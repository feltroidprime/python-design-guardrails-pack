"""The eight refusals of a Pack Update, and the one promise each one ends with.

`U1` to `U8` of #85 section 4.2 are one rule each, and `U4` is one rule with two
cases: the destination is not a git repository, or its worktree is dirty
(conflict C17 of #85). Each case below provokes one rule against a real tree,
and each one measures the same three facts: the message names the rule, it ends
with the promise, and the tree did not change.

An equal version is not a refusal. `test_update.py` measures that one, because
it is a run that succeeds.

These cases prepare assertion `UPD-8` of #81, and the `U7` case prepares `REM-6`.
"""

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import cast

import pytest

from guardrails_pack.bootstrap.adapters.outbound.payload import InstalledPayload
from guardrails_pack.bootstrap.application.update import UpdateRequest, update_project
from guardrails_pack.bootstrap.domain.errors import NOTHING_WAS_WRITTEN, RefusalError
from guardrails_pack.bootstrap.tests.conftest import (
    CAPABILITY,
    MANIFEST,
    PACK_PACKAGE,
    PACK_ROOT_SURFACE,
    PROJECT_PACKAGE,
    Worktree,
    build_archive,
    write_destination,
    write_release,
)

OLD = "0.1.0"
NEW = "0.2.0"
LATER = "0.9.0"
GIT_DIRECTORY = ".git"


def tree_hashes(root: Path) -> dict[str, str]:
    """The sha256 of every file of one tree, the git database apart."""
    return {
        path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and GIT_DIRECTORY not in path.relative_to(root).parts
    }


def refusal(
    tmp_path: Path,
    destination: Path,
    *,
    release: Path | None = None,
    runner: Worktree | None = None,
) -> str:
    """Run one update that must refuse, and return its message."""
    source = write_release(tmp_path / "next", NEW) if release is None else release
    payload = InstalledPayload(archive=build_archive(source, tmp_path / "next.tar"))
    before = tree_hashes(destination)
    request = UpdateRequest(destination=destination, force=False)
    with pytest.raises(RefusalError) as raised:
        _ = update_project(payload, runner or Worktree(), request, CAPABILITY)
    assert tree_hashes(destination) == before
    message = str(raised.value)
    assert message.endswith(NOTHING_WAS_WRITTEN)
    return message


def with_version(destination: Path, version: str) -> Path:
    """Rewrite the version the project records, and keep every hash it records."""
    path = destination / MANIFEST
    record = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    record["pack_version"] = version
    _ = path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def test_u1_refuses_a_destination_that_records_no_manifest(tmp_path: Path) -> None:
    destination = write_destination(tmp_path / "project", OLD)
    (destination / MANIFEST).unlink()

    assert "U1" in refusal(tmp_path, destination)


def test_u2_refuses_a_destination_whose_package_cannot_be_derived(tmp_path: Path) -> None:
    destination = write_destination(tmp_path / "project", OLD)
    (destination / "src" / "second_package").mkdir()

    assert "U2" in refusal(tmp_path, destination)


def test_u3_refuses_a_project_that_records_a_newer_version(tmp_path: Path) -> None:
    destination = with_version(write_destination(tmp_path / "project", OLD), LATER)

    assert "U3" in refusal(tmp_path, destination)


def test_u4_refuses_a_destination_that_is_not_a_git_repository(tmp_path: Path) -> None:
    destination = write_destination(tmp_path / "project", OLD)

    assert "U4" in refusal(tmp_path, destination, runner=Worktree(present=False))


def test_u4_refuses_a_dirty_worktree(tmp_path: Path) -> None:
    destination = write_destination(tmp_path / "project", OLD)
    dirty = Worktree(dirty=" M README.md\n")

    assert "U4" in refusal(tmp_path, destination, runner=dirty)


def test_u5_refuses_a_pack_owned_file_that_drifted(tmp_path: Path) -> None:
    destination = write_destination(tmp_path / "project", OLD)
    _ = (destination / "pack" / "justfile").write_text("check:\n    echo mine\n", encoding="utf-8")

    assert "U5" in refusal(tmp_path, destination)


def test_u6_refuses_a_plan_that_names_a_user_owned_path(tmp_path: Path) -> None:
    claimed = "README.md"
    claiming: Mapping[str, str] = {**PACK_ROOT_SURFACE, claimed: "# The pack claims this.\n"}
    release = write_release(tmp_path / "next", NEW, root_surface=claiming)
    destination = write_destination(tmp_path / "project", OLD)

    message = refusal(tmp_path, destination, release=release)

    assert "U6" in message
    assert claimed in message


def test_u7_refuses_a_root_pack_as_the_destination(tmp_path: Path) -> None:
    destination = write_destination(tmp_path / "project", OLD)
    capability = destination / "src" / PROJECT_PACKAGE / CAPABILITY
    capability.mkdir(parents=True)
    _ = (capability / "api.py").write_text('"""Project this pack."""\n', encoding="utf-8")

    assert "U7" in refusal(tmp_path, destination)


def test_u8_refuses_an_installed_pack_whose_manifest_is_stale(tmp_path: Path) -> None:
    release = write_release(tmp_path / "next", NEW)
    _ = (release / "src" / PACK_PACKAGE / "_foundation" / "router.py").write_text(
        '"""The router, changed after the record was written."""\n', encoding="utf-8"
    )
    destination = write_destination(tmp_path / "project", OLD)

    assert "U8" in refusal(tmp_path, destination, release=release)
