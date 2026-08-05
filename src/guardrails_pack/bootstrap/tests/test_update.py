"""What one Pack Update does to a real tree, and what it never does to one.

Each case below states one measured property of #82 as it is recorded in #85,
and each one prepares one assertion of the `UPD` group of #81. The acceptance
suite runs the same properties from the installed console script, against the
whole tree; these cases run them against a small tree, in one process.

Every case drives a committed git checkout and reads `git status --porcelain`,
because that is the boundary the promise is stated at: an update writes
pack-owned paths, and git is the undo of them.
"""

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest

from guardrails_pack.bootstrap.adapters.outbound.commands import LocalCommands
from guardrails_pack.bootstrap.adapters.outbound.payload import InstalledPayload
from guardrails_pack.bootstrap.application.update import UpdateRequest, update_project
from guardrails_pack.bootstrap.domain.errors import NOTHING_WAS_WRITTEN, RefusalError
from guardrails_pack.bootstrap.tests.conftest import (
    CAPABILITY,
    MANIFEST,
    PACK_PACKAGE_SURFACE,
    PACK_ROOT_SURFACE,
    PROJECT_PACKAGE,
    SHIM_CONTENTS,
    build_archive,
    write_destination,
    write_release,
)

OLD = "0.1.0"
NEW = "0.2.0"
GIT_DIRECTORY = ".git"
DRIFT_DIRECTORY = "pack/.drift"
STATUS = ("git", "status", "--porcelain")
READ_ONLY = 0o500
WRITABLE = 0o755

# The next release: one file changed, two files added, one file dropped.
NEXT_ROOT_SURFACE: Mapping[str, str] = MappingProxyType(
    {
        "pack/.gitignore": ".drift/\n",
        "pack/configs/pytest.ini": "[pytest]\n",
        "pack/justfile": "check:\n    prek run --all-files -c pack/configs/prek.toml\n",
        "pack/scripts/guard.py": '"""One pack-owned guard."""\n',
        "pack/scripts/second_guard.py": '"""One more pack-owned guard."""\n',
    }
)


class Tracked:
    """`LocalCommands`, with every command it was asked for kept in order."""

    def __init__(self) -> None:
        """Run real commands, and record the program and arguments of each one."""
        self.commands: list[tuple[str, ...]] = []
        self.local: LocalCommands = LocalCommands()

    def run(self, command: Sequence[str], directory: Path, /) -> None:
        """Run one command."""
        self.commands.append(tuple(command))
        self.local.run(command, directory)

    def succeeds(self, command: Sequence[str], directory: Path, /) -> bool:
        """Run one command and report whether it ended with zero."""
        self.commands.append(tuple(command))
        return self.local.succeeds(command, directory)

    def read(self, command: Sequence[str], directory: Path, /) -> str:
        """Run one command and return its standard output as text."""
        self.commands.append(tuple(command))
        return self.local.read(command, directory)


def payload_for(tree: Path, workspace: Path, name: str) -> InstalledPayload:
    """One projection payload built from one release tree."""
    return InstalledPayload(archive=build_archive(tree, workspace / f"{name}.tar"))


def tree_hashes(root: Path) -> dict[str, str]:
    """The sha256 of every file of one tree, the git database apart."""
    return {
        path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and GIT_DIRECTORY not in path.relative_to(root).parts
    }


def status_of(destination: Path) -> tuple[str, ...]:
    """Every path that `git status --porcelain` names, in order."""
    lines = LocalCommands().read(STATUS, destination).splitlines()
    return tuple(line[3:].strip() for line in lines if line.strip())


def updated(
    tmp_path: Path,
    destination: Path,
    *,
    force: bool = False,
    runner: Tracked | None = None,
) -> dict[str, object]:
    """Run one update of *destination* from a release that ships `NEXT_ROOT_SURFACE`."""
    release = write_release(tmp_path / "next", NEW, root_surface=NEXT_ROOT_SURFACE)
    request = UpdateRequest(destination=destination, force=force)
    payload = payload_for(release, tmp_path, "next")
    return update_project(payload, runner or Tracked(), request, CAPABILITY)


@pytest.fixture
def destination(tmp_path: Path) -> Path:
    """One committed project born from the release before the installed one."""
    return write_destination(tmp_path / "project", OLD)


def test_an_update_leaves_every_user_owned_file_byte_identical(
    tmp_path: Path, destination: Path
) -> None:
    before = tree_hashes(destination)

    report = updated(tmp_path, destination)

    user_owned = {
        relative: recorded
        for relative, recorded in before.items()
        if not relative.startswith(("pack/", f"src/{PROJECT_PACKAGE}/_"))
    }
    after = tree_hashes(destination)
    assert {relative: after[relative] for relative in user_owned} == user_owned
    assert report["written"] == 5


def test_the_update_writes_pack_owned_paths_only(tmp_path: Path, destination: Path) -> None:
    _ = updated(tmp_path, destination)

    changed = status_of(destination)
    assert changed
    assert all(path.startswith("pack/") for path in changed)


def test_the_update_classifies_the_release_as_added_replaced_and_deleted(
    tmp_path: Path, destination: Path
) -> None:
    report = updated(tmp_path, destination)

    assert report["added"] == ["pack/configs/pytest.ini", "pack/scripts/second_guard.py"]
    assert report["replaced"] == ["pack/justfile"]
    assert report["deleted"] == ["pack/configs/ruff.toml"]
    assert report["previous_version"] == OLD
    assert report["pack_version"] == NEW


def test_a_second_update_writes_nothing_and_leaves_the_worktree_clean(
    tmp_path: Path, destination: Path
) -> None:
    _ = updated(tmp_path, destination)
    LocalCommands().run(("git", "add", "--all"), destination)
    LocalCommands().run(("git", "commit", "--quiet", "--message", "Update"), destination)

    report = updated(tmp_path, destination)

    assert report["written"] == 0
    assert status_of(destination) == ()


def test_an_equal_version_writes_nothing_and_is_not_a_refusal(tmp_path: Path) -> None:
    same = write_destination(tmp_path / "current", NEW, root_surface=NEXT_ROOT_SURFACE)

    report = updated(tmp_path, same)

    assert report["written"] == 0
    assert status_of(same) == ()


def test_a_failed_write_restores_every_path(tmp_path: Path, destination: Path) -> None:
    before = tree_hashes(destination)
    blocked = destination / "pack" / "scripts"
    blocked.chmod(READ_ONLY)

    try:
        with pytest.raises(OSError, match=r"[Pp]ermission"):
            _ = updated(tmp_path, destination)
        assert tree_hashes(destination) == before
        assert status_of(destination) == ()
    finally:
        blocked.chmod(WRITABLE)

    report = updated(tmp_path, destination)

    assert report["written"] == 5


def test_drift_of_one_pack_owned_file_refuses_and_writes_nothing(
    tmp_path: Path, destination: Path
) -> None:
    edited = destination / "pack" / "justfile"
    _ = edited.write_text("check:\n    echo mine\n", encoding="utf-8")
    LocalCommands().run(("git", "add", "--all"), destination)
    LocalCommands().run(("git", "commit", "--quiet", "--message", "Local edit"), destination)
    before = tree_hashes(destination)

    with pytest.raises(RefusalError) as raised:
        _ = updated(tmp_path, destination)

    assert "U5" in str(raised.value)
    assert str(raised.value).endswith(NOTHING_WAS_WRITTEN)
    assert tree_hashes(destination) == before


def test_force_saves_the_replaced_bytes_and_git_lists_only_written_paths(
    tmp_path: Path, destination: Path
) -> None:
    edited = destination / "pack" / "justfile"
    mine = "check:\n    echo mine\n"
    _ = edited.write_text(mine, encoding="utf-8")
    LocalCommands().run(("git", "add", "--all"), destination)
    LocalCommands().run(("git", "commit", "--quiet", "--message", "Local edit"), destination)

    report = updated(tmp_path, destination, force=True)

    saved = destination / DRIFT_DIRECTORY / "pack" / "justfile"
    assert saved.read_text(encoding="utf-8") == mine
    assert report["forced"] is True
    assert set(status_of(destination)) == {
        "pack/configs/pytest.ini",
        "pack/configs/ruff.toml",
        "pack/justfile",
        "pack/manifest.json",
        "pack/scripts/second_guard.py",
    }


def test_the_manifest_states_the_new_tree_after_the_update(
    tmp_path: Path, destination: Path
) -> None:
    report = updated(tmp_path, destination)

    recorded = cast(
        "dict[str, dict[str, str]]",
        json.loads((destination / MANIFEST).read_text(encoding="utf-8")),
    )
    assert recorded["pack_version"] == NEW
    assert set(recorded["root"]) == set(NEXT_ROOT_SURFACE)
    assert set(recorded["package"]) == set(PACK_PACKAGE_SURFACE)
    assert report["pack_version"] == recorded["pack_version"]


def test_the_manifest_is_written_last(tmp_path: Path, destination: Path) -> None:
    blocked = destination / "pack" / "scripts"
    blocked.chmod(READ_ONLY)

    try:
        with pytest.raises(OSError, match=r"[Pp]ermission"):
            _ = updated(tmp_path, destination)
        recorded = cast(
            "dict[str, dict[str, str]]",
            json.loads((destination / MANIFEST).read_text(encoding="utf-8")),
        )
    finally:
        blocked.chmod(WRITABLE)

    assert recorded["pack_version"] == OLD
    assert set(recorded["root"]) == set(PACK_ROOT_SURFACE)


def test_a_customised_shim_is_reported_and_never_written(tmp_path: Path, destination: Path) -> None:
    shim = destination / "justfile"
    mine = "import 'pack/justfile'\n\nmine:\n    echo mine\n"
    _ = shim.write_text(mine, encoding="utf-8")
    LocalCommands().run(("git", "add", "--all"), destination)
    LocalCommands().run(("git", "commit", "--quiet", "--message", "My recipe"), destination)

    report = updated(tmp_path, destination)

    shims = cast("list[dict[str, object]]", report["shims"])
    reported = {str(entry["path"]): str(entry["state"]) for entry in shims}
    assert reported == {
        ".github/workflows/quality.yml": "untouched",
        ".python-version": "untouched",
        "justfile": "customised",
        "pyrightconfig.json": "untouched",
    }
    assert shim.read_text(encoding="utf-8") == mine
    assert set(SHIM_CONTENTS).isdisjoint(status_of(destination))


def test_the_update_runs_no_gate_command(tmp_path: Path, destination: Path) -> None:
    runner = Tracked()

    _ = updated(tmp_path, destination, runner=runner)

    assert {command[0] for command in runner.commands} == {"git"}
