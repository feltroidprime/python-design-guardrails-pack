"""Group 4 of #81, second half: `UPD-8` to `UPD-13`.

`UPD-8` fires every refusal of the update protocol against a real tree. Rules
`R4` and `R5` belong to `init` rather than to `update`, because an update has no
name to admit and no destination to create, so both are driven through `init`
here and the ten rules of #82 are covered together.

`UPD-11` and the manifest assertions read the `manifest` hook, which is refusal
`U8` read from the inside at commit time.
"""

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from guardrails_pack.bootstrap.tests.acceptance.code import CAPABILITY, status_locations
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project, project_once
from guardrails_pack.bootstrap.tests.acceptance.harness import (
    Outcome,
    gate,
    git,
    porcelain,
    run,
    sync,
)
from guardrails_pack.bootstrap.tests.acceptance.packs import (
    POLICY_PROBE,
    Pack,
    claiming_release,
    stale_release,
)
from guardrails_pack.bootstrap.tests.acceptance.updates import (
    manifest_of,
    update,
    user_owned,
    write_manifest_record,
)

MANIFEST_HOOK = "manifest"
FORMAT_HOOK = "format"
SHIM = "justfile"
DRIFTED_FILE = "pack/configs/ruff.toml"
NEWER_VERSION = "99.0.0"
CUSTOM_RECIPE = "\n# One recipe of my own.\nmine:\n    @echo mine\n"
WIDE_PROBE = POLICY_PROBE
# One statement of 121 columns. The previous release excludes this file name
# from every Ruff rule and the current release checks it, so `format` reads the
# policy that the update carried.
WIDE_SOURCE = (
    "VALUE = {"
    '"alpha": 1, "bravo": 2, "charlie": 3, "delta": 4, "echo": 5, "foxtrot": 6, '
    '"golf": 7, "hotel": 8, "india": 9}\n'
)
NOTHING_WAS_WRITTEN = "Nothing was written."
ACCEPTANCE = "acceptance"


def refused(outcome: Outcome, rule: str) -> bool:
    """One refusal names its rule, ends with the promise, and exits non-zero."""
    return outcome.code != 0 and f"{rule}: " in outcome.text and NOTHING_WAS_WRITTEN in outcome.text


def commit(tree: Path, message: str) -> None:
    """Record every change of *tree*, so the worktree is clean again."""
    _ = git(tree, "add", "--all")
    _ = git(tree, "commit", "--quiet", "--message", message)


def _u1(tree: Path) -> None:
    (tree / "pack" / "manifest.json").unlink()


def _u2(tree: Path) -> None:
    (tree / "src" / "second_package").mkdir()
    _ = (tree / "src" / "second_package" / "__init__.py").write_text("", encoding="utf-8")


def _u3(tree: Path) -> None:
    record = manifest_of(tree)
    record["pack_version"] = NEWER_VERSION
    _ = write_manifest_record(tree, record)


def _u5(tree: Path) -> None:
    target = tree / DRIFTED_FILE
    _ = target.write_text(target.read_text("utf-8") + "# One local edit.\n", encoding="utf-8")


def _u7(tree: Path, package: str) -> None:
    (tree / "src" / package / CAPABILITY).mkdir(parents=True)


REFUSALS: tuple[tuple[str, Callable[[Path, str], None]], ...] = (
    ("U1", lambda tree, _package: _u1(tree)),
    ("U2", lambda tree, _package: _u2(tree)),
    ("U3", lambda tree, _package: _u3(tree)),
    ("U5", lambda tree, _package: _u5(tree)),
    ("U7", _u7),
)


@pytest.mark.parametrize(("rule", "inject"), REFUSALS, ids=[rule for rule, _ in REFUSALS])
def test_upd_8_each_committed_refusal_fires(
    old: Project, toolenv: Pack, rule: str, inject: Callable[[Path, str], None]
) -> None:
    """`UPD-8`: one case per rule, each of which writes nothing."""
    inject(old.path, old.tokens.package)
    commit(old.path, f"The tree that {rule} refuses")

    report = update(toolenv, old.path)

    assert refused(report.outcome, rule), report.outcome.text
    assert porcelain(old.path) == ()


def test_upd_8_u4_refuses_a_tree_that_is_not_a_repository(old: Project, toolenv: Pack) -> None:
    """`UPD-8`, `U4` first case: git is the only way back from a whole-file update."""
    for item in sorted((old.path / ".git").rglob("*"), reverse=True):
        item.chmod(0o700)
    _ = run(("rm", "-rf", str(old.path / ".git")), old.path)

    report = update(toolenv, old.path)

    assert refused(report.outcome, "U4"), report.outcome.text


def test_upd_8_u4_refuses_a_dirty_worktree(old: Project, toolenv: Pack) -> None:
    """`UPD-8`, `U4` second case: conflict `C17`, one rule with two cases."""
    _ = (old.path / "README.md").write_text("My own note.\n", encoding="utf-8")

    report = update(toolenv, old.path)

    assert refused(report.outcome, "U4"), report.outcome.text
    assert status_locations(porcelain(old.path)) == ("README.md",)


def test_upd_8_u6_refuses_a_plan_that_claims_a_user_owned_path(
    old: Project, root: Path, work: Path
) -> None:
    """`UPD-8`, `U6`: the plan is read through the predicate before any write."""
    claiming = claiming_release(root, work)

    report = update(claiming, old.path)

    assert refused(report.outcome, "U6"), report.outcome.text
    assert porcelain(old.path) == ()


def test_upd_8_u8_refuses_a_pack_whose_record_is_stale(
    old: Project, root: Path, work: Path
) -> None:
    """`UPD-8`, `U8`: a stale record makes an update read a changed file as untouched."""
    stale = stale_release(root, work)

    report = update(stale, old.path)

    assert refused(report.outcome, "U8"), report.outcome.text
    assert porcelain(old.path) == ()


def test_upd_8_r4_and_r5_refuse_through_init(toolenv: Pack, work: Path) -> None:
    """`UPD-8`, `R4` and `R5`: the two rules of the protocol that `init` owns."""
    taken = work / "upd8-taken"
    taken.mkdir(exist_ok=True)

    same_name = project_once(toolenv.script, toolenv.tokens.project, work / "upd8-name")
    existing = project_once(toolenv.script, "taken-thing", taken)

    assert refused(same_name.outcome, "R4"), same_name.outcome.text
    assert refused(existing.outcome, "R5"), existing.outcome.text


def test_upd_9_an_equal_version_is_not_a_refusal(old: Project, toolenv: Pack) -> None:
    """`UPD-9`: a no-op reported as an error would make every retry unsafe."""
    first = update(toolenv, old.path)
    assert first.outcome.code == 0, first.outcome.text
    commit(old.path, "The update")

    second = update(toolenv, old.path)

    assert second.outcome.code == 0, second.outcome.text
    assert second.written == 0


def test_upd_10_the_manifest_is_written_last_and_is_true(old: Project, toolenv: Pack) -> None:
    """`UPD-10`: a record that lied about the tree would break every later update."""
    report = update(toolenv, old.path)
    assert report.outcome.code == 0, report.outcome.text
    _ = sync(old.path)

    hook = gate(old.path, MANIFEST_HOOK)

    assert hook.code == 0, hook.text
    assert manifest_of(old.path)["pack_version"] == report.data.get("pack_version")


def test_upd_11_a_stale_manifest_turns_the_gate_red(root: Path) -> None:
    """`UPD-11`: refusal `U8` read from the inside, moved to commit time."""
    target = root / DRIFTED_FILE
    original = target.read_bytes()
    try:
        _ = target.write_bytes(original + b"# One hand edit.\n")
        red = gate(root, MANIFEST_HOOK)
    finally:
        _ = target.write_bytes(original)
    green = gate(root, MANIFEST_HOOK)

    assert red.code != 0, red.text
    assert green.code == 0, green.text


def test_upd_12_an_update_carries_policy_and_never_runs_the_gate(
    old: Project, toolenv: Pack
) -> None:
    """`UPD-12`: a red gate on user code after an update is the intended signal."""
    probe = f"src/{old.tokens.package}/{WIDE_PROBE}"
    _ = (old.path / probe).write_text(WIDE_SOURCE, encoding="utf-8")
    commit(old.path, "One wide line of my own")
    _ = sync(old.path)
    before = gate(old.path, FORMAT_HOOK)
    owned = user_owned(old.path, old.tokens.package)

    report = update(toolenv, old.path)

    assert before.code == 0, before.text
    assert report.outcome.code == 0, report.outcome.text
    assert user_owned(old.path, old.tokens.package) == owned
    after = gate(old.path, FORMAT_HOOK)
    assert after.code != 0
    assert WIDE_PROBE in after.text


def test_upd_13_a_customised_shim_is_reported_and_never_written(
    old: Project, toolenv: Pack
) -> None:
    """`UPD-13`: an update that rewrote a user-owned entry point would erase work."""
    shim = old.path / SHIM
    mine = shim.read_text("utf-8") + CUSTOM_RECIPE
    _ = shim.write_text(mine, encoding="utf-8")
    commit(old.path, "One recipe of my own")

    report = update(toolenv, old.path)

    assert report.outcome.code == 0, report.outcome.text
    assert shim.read_text("utf-8") == mine
    assert SHIM not in status_locations(porcelain(old.path))
    reported = [line for line in report.shims if line.get("path") == SHIM]
    assert reported, report.shims
    assert reported[0].get("state") != "unchanged", report.shims


def test_the_suite_is_marked_acceptance(request: pytest.FixtureRequest) -> None:
    """Rule `H3`: the `tests` hook of the gate runs `-m "not acceptance"`."""
    node = cast("pytest.Item", request.node)

    assert {mark.name for mark in node.own_markers} >= {ACCEPTANCE}
