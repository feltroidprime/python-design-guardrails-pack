"""Group 4 of #81, first half: safe whole-file updates, `UPD-1` to `UPD-7`.

`OLD` is a Terminal Project of the previous release, and the current wheel
carries one real `ADD`, one real `REPLACE` and one real `DELETE` on the
Pack-owned Surface. Every assertion runs the update from the installed console
script and reads the tree from the outside only.
"""

from pathlib import Path

from guardrails_pack.bootstrap.tests.acceptance.code import pack_owned, status_locations
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project
from guardrails_pack.bootstrap.tests.acceptance.harness import (
    failing_hooks,
    git,
    make_repository,
    porcelain,
)
from guardrails_pack.bootstrap.tests.acceptance.packs import (
    ADDED_BY_NEW,
    DELETED_BY_NEW,
    REPLACED_BY_NEW,
    Pack,
)
from guardrails_pack.bootstrap.tests.acceptance.updates import update, user_owned

DRIFT_DIRECTORY = "pack/.drift"
DRIFT_RULE = ".drift/"
READ_ONLY = 0o500
WRITABLE = 0o755
DRIFTED_FILE = "pack/configs/ruff.toml"
DRIFT_LINE = "# One local edit of a pack-owned file.\n"


def test_upd_1_every_user_owned_file_is_byte_identical(old: Project, toolenv: Pack) -> None:
    """`UPD-1`: an update that reached user code would be unrecoverable in silence."""
    before = user_owned(old.path, old.tokens.package)

    report = update(toolenv, old.path)

    assert report.outcome.code == 0, report.outcome.text
    assert user_owned(old.path, old.tokens.package) == before


def test_upd_2_every_written_path_satisfies_the_predicate(old: Project, toolenv: Pack) -> None:
    """`UPD-2`: Code E over the plan and over `git status --porcelain` (refusal `U6`)."""
    report = update(toolenv, old.path)

    planned = report.planned
    changed = status_locations(porcelain(old.path))

    assert report.outcome.code == 0, report.outcome.text
    assert planned
    assert [path for path in planned if not pack_owned(path, old.tokens.package)] == []
    assert [path for path in changed if not pack_owned(path, old.tokens.package)] == []


def test_upd_2_the_three_release_changes_are_real(old: Project, toolenv: Pack) -> None:
    """`UPD-2`: the release under test carries one add, one replace and one delete."""
    report = update(toolenv, old.path)

    assert report.locations("added") == (ADDED_BY_NEW,)
    assert REPLACED_BY_NEW in report.locations("replaced")
    assert report.locations("deleted") == (DELETED_BY_NEW,)


def test_upd_3_the_update_is_idempotent(old: Project, toolenv: Pack) -> None:
    """`UPD-3`: a project that repeated the same writes for ever would never settle."""
    first = update(toolenv, old.path)
    assert first.outcome.code == 0, first.outcome.text
    _ = make_repository(old.path, "The update")

    second = update(toolenv, old.path)

    assert second.outcome.code == 0, second.outcome.text
    assert second.written == 0
    assert porcelain(old.path) == ()


def test_upd_4_a_crash_leaves_the_tree_unchanged(old: Project, toolenv: Pack) -> None:
    """`UPD-4`: the user must never be left with a half-written tree to clean."""
    before = {
        relative: (old.path / relative).read_bytes()
        for relative in (REPLACED_BY_NEW, DELETED_BY_NEW)
    }
    blocked = old.path / "pack" / "configs"
    blocked.chmod(READ_ONLY)
    try:
        crashed = update(toolenv, old.path)
    finally:
        blocked.chmod(WRITABLE)

    assert crashed.outcome.code != 0
    assert {name: (old.path / name).read_bytes() for name in before} == before
    assert porcelain(old.path) == ()

    retried = update(toolenv, old.path)

    assert retried.outcome.code == 0, retried.outcome.text


def drift(tree: Path) -> None:
    """Change one pack-owned file by hand, and commit it as a user would."""
    target = tree / DRIFTED_FILE
    _ = target.write_text(target.read_text("utf-8") + DRIFT_LINE, encoding="utf-8")
    _ = git(tree, "add", "--all")
    _ = git(tree, "commit", "--quiet", "--message", "One local edit")


def test_upd_5_drift_refuses(old: Project, toolenv: Pack) -> None:
    """`UPD-5`: an update that discarded user work in silence would be unforgivable."""
    drift(old.path)
    before = (old.path / REPLACED_BY_NEW).read_bytes()

    refused = update(toolenv, old.path)

    assert refused.outcome.code != 0
    assert "U5: " in refused.outcome.text
    assert (old.path / REPLACED_BY_NEW).read_bytes() == before
    assert porcelain(old.path) == ()


def test_upd_6_force_is_bounded_and_recoverable(old: Project, toolenv: Pack) -> None:
    """`UPD-6`: a force that wrote outside its plan would be a second defect."""
    drift(old.path)
    replaced = (old.path / DRIFTED_FILE).read_bytes()

    forced = update(toolenv, old.path, force=True)

    assert forced.outcome.code == 0, forced.outcome.text
    changed = status_locations(porcelain(old.path))
    assert [path for path in changed if not pack_owned(path, old.tokens.package)] == []
    assert (old.path / DRIFT_DIRECTORY / DRIFTED_FILE).read_bytes() == replaced


def test_upd_7_the_drift_directory_is_ignored_by_a_pack_owned_file(
    old: Project, toolenv: Pack
) -> None:
    """`UPD-7`: an ignore rule in the root file could never reach an existing project."""
    baseline = failing_hooks(old.path)
    drift(old.path)
    forced = update(toolenv, old.path, force=True)
    assert forced.outcome.code == 0, forced.outcome.text

    pack_ignore = (old.path / "pack" / ".gitignore").read_text(encoding="utf-8")
    root_ignore = (old.path / ".gitignore").read_text(encoding="utf-8")

    assert DRIFT_RULE in pack_ignore
    assert ".drift" not in root_ignore
    assert [path for path in status_locations(porcelain(old.path)) if DRIFT_DIRECTORY in path] == []
    assert failing_hooks(old.path) <= baseline
