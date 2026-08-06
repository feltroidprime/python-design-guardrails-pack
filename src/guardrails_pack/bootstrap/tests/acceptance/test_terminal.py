"""A Terminal Project cannot generate another repository.

`TER-1` to `TER-7` state a clean project file, a clean wheel, a clean virtual
environment, the two payload rules, and both projection sources.

`TER-6` and the gate pull against each other: the gate must ignore the staged
payload, so the gate definition has to state it, and `pack/` reaches a Terminal
Project byte for byte. The gate and the manifest script ignore every archive
directly under a source package, and neither one holds the file name. A
name-blind rule also covers every archive an interrupted build can leave, not
one spelling.
"""

from pathlib import Path
import zipfile

from guardrails_pack.bootstrap.tests.acceptance.code import CAPABILITY, Tokens, compare, grep
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project, derived_package
from guardrails_pack.bootstrap.tests.acceptance.harness import Outcome, failing_hooks, run, sync
from guardrails_pack.bootstrap.tests.acceptance.packs import Pack, staged_payload

PACK_ONLY_MARKERS = ("force-include", "_pack")
ARCHIVE_SUFFIX = ".tar"
PACK_DIRECTORY = "pack/"
PAYLOAD_INSTRUCTIONS = r"_pack\.tar|git archive"
CHECKOUT_NAME = "checkout-thing"
STAGED_NAME = "staged-thing"


def token_pattern(tokens: Tokens) -> str:
    """A grep pattern that matches either pack token."""
    return f"{tokens.project}|{tokens.package}"


def project_from_checkout(root: Path, tokens: Tokens, name: str, destination: Path) -> Project:
    """Run `init` from the Root Pack's own checkout, the second payload source."""
    outcome: Outcome = run(
        ("uv", "run", tokens.project, CAPABILITY, "init", name, str(destination)),
        root,
    )
    return Project(
        path=destination,
        tokens=Tokens(project=name, package=derived_package(name)),
        outcome=outcome,
    )


def archives_under_source(tree: Path) -> list[Path]:
    """Every archive that sits directly under a package of `src/`."""
    return sorted((tree / "src").glob(f"*/*{ARCHIVE_SUFFIX}"))


def test_ter_1_the_project_file_holds_no_pack_only_packaging(term: Project) -> None:
    """`TER-1`: a stanza inside the projected file could not erase itself."""
    text = (term.path / "pyproject.toml").read_text(encoding="utf-8")

    assert [marker for marker in PACK_ONLY_MARKERS if marker in text] == []


def test_ter_2_the_terminal_wheel_carries_no_pack_tree(term: Project, tmp_path: Path) -> None:
    """`TER-2`: duplicated source shipped to the users of a user's product."""
    built = run(("uv", "build", "--wheel", "-o", str(tmp_path)), term.path)
    assert built.code == 0, built.text
    wheels = sorted(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, wheels

    with zipfile.ZipFile(wheels[0]) as opened:
        members = tuple(opened.namelist())

    assert [name for name in members if name.endswith(ARCHIVE_SUFFIX)] == []
    assert [name for name in members if PACK_DIRECTORY in name] == []


def test_ter_3_the_virtual_environment_carries_no_pack_tree(term: Project) -> None:
    """`TER-3`: the same defect, which the wheel assertion alone misses.

    The reading is the installed distribution under `.venv/lib`, which is what
    `uv sync` writes. `.venv/pycache` holds the bytecode mirror that the tree
    exports through `PYTHONPYCACHEPREFIX`, so it carries a compiled copy of the
    tree's own pack scripts by design and states nothing about packaging.
    """
    _ = sync(term.path)

    found = run(
        (
            "find",
            str(term.path / ".venv" / "lib"),
            "-name",
            f"*{ARCHIVE_SUFFIX}",
            "-o",
            "-path",
            f"*/{PACK_DIRECTORY}scripts/*",
        ),
        term.path,
    )

    assert found.out.strip() == ""


def test_ter_4_the_gate_ignores_the_staged_payload(root: Path, toolenv: Pack) -> None:
    """`TER-4`: an interrupted build must never turn the gate red."""
    before = failing_hooks(root)
    payload = staged_payload(root, toolenv.tokens)
    try:
        _ = payload.write_bytes(toolenv.wheel.read_bytes())
        after = failing_hooks(root)
    finally:
        payload.unlink(missing_ok=True)

    assert after == before


def test_ter_5_projection_excludes_the_staged_payload(
    root: Path, toolenv: Pack, work: Path
) -> None:
    """`TER-5`: a leftover payload would copy the whole pack into a project."""
    payload = staged_payload(root, toolenv.tokens)
    destination = work / "staged"
    try:
        made = run(("git", "archive", "HEAD", "-o", str(payload)), root)
        assert made.code == 0, made.text
        projected = project_from_checkout(root, toolenv.tokens, STAGED_NAME, destination)
    finally:
        payload.unlink(missing_ok=True)

    assert (projected.path / "pyproject.toml").is_file(), projected.outcome.text
    assert archives_under_source(projected.path) == []
    assert grep(projected.path, token_pattern(toolenv.tokens)) == ()


def test_ter_6_no_pack_only_instruction_survives(term: Project) -> None:
    """`TER-6`: the hatchling defect at small scale, settled by a name-blind rule."""
    found = grep(term.path, PAYLOAD_INSTRUCTIONS)

    assert found == ()


def test_ter_7_the_projection_source_has_two_locations(
    root: Path, term: Project, toolenv: Pack, work: Path
) -> None:
    """`TER-7`: the checkout fallback, which nothing else exercises.

    Both trees must pass `PAR-4`, `PAR-6` and `REM-1`, so the two sources give
    one product and the fallback can never drift away from the shipped archive.
    """
    made = project_from_checkout(root, toolenv.tokens, CHECKOUT_NAME, work / "checkout")
    assert (made.path / "pyproject.toml").is_file(), made.outcome.text

    for tree in (term, made):
        parity = compare(root, tree.path, toolenv.tokens, tree.tokens)
        assert grep(tree.path, token_pattern(toolenv.tokens)) == ()
        assert parity.changed == frozenset()
        assert list(tree.path.rglob(CAPABILITY)) == []
