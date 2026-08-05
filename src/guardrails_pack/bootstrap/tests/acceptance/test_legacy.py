"""Group 3 of #81: absence of legacy architecture and vocabulary, `LEG-1` to `LEG-6`.

The group certifies the deletion boundary of #85 section 1, the twelve hooks of
section 4.4, a green gate in both trees, and a gate definition that a pack update
can replace whole.

`LEG-1` and `LEG-2` are the two ban lists of Code B. Three exemptions apply, all
stated in `ban_lists.py`: that module itself, and, in the Root Pack only,
`CHANGELOG.md` and `docs/vendored/`.
"""

from pathlib import Path

import pytest

from guardrails_pack.bootstrap.tests.acceptance.ban_lists import (
    EXEMPT_IN_PACK,
    IDENTIFIER_PATTERN,
    PROSE_PATTERN,
    PROSE_SUFFIXES,
    SOURCE_FILE,
)
from guardrails_pack.bootstrap.tests.acceptance.code import gate_hook_ids, grep
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project
from guardrails_pack.bootstrap.tests.acceptance.harness import failing_hooks, gate

TWELVE_HOOKS = frozenset(
    {
        "lockfile",
        "format",
        "lint",
        "types",
        "dependencies",
        "architecture",
        "docs",
        "proof",
        "symbolic",
        "import-contracts",
        "tests",
        "manifest",
    }
)
LEGACY_PATHS = (
    "template",
    "copier.yml",
    "instantiate.py",
    "scripts/quality_gate.py",
    ".repo",
    "proof/modules",
    "tests/modules",
    "verification/modules",
    "docs/product",
)
GENERATED_PACKAGE_DIRECTORY = "_generated"


def exempt(line: str, *names: str) -> bool:
    """Whether one grep line names a file that its own list exempts."""
    return any(name in line for name in names)


def test_leg_1_no_legacy_identifier_in_the_pack(root: Path) -> None:
    """`LEG-1` on `ROOT`: Code B, list 1, including the three coverage strings."""
    found = grep(root, IDENTIFIER_PATTERN, "--exclude-dir=.venv")

    assert [line for line in found if not exempt(line, SOURCE_FILE, *EXEMPT_IN_PACK)] == []


def test_leg_1_no_legacy_identifier_in_a_project(term: Project) -> None:
    """`LEG-1` on `TERM`: a fresh project needs no exemption but the list itself."""
    found = grep(term.path, IDENTIFIER_PATTERN, "--exclude-dir=.venv")

    assert [line for line in found if not exempt(line, SOURCE_FILE)] == []


def test_leg_2_no_legacy_prose_in_the_pack(root: Path) -> None:
    """`LEG-2` on `ROOT`: Code B, list 2, over Markdown and Python only."""
    includes = tuple(f"--include={suffix}" for suffix in PROSE_SUFFIXES)
    found = grep(root, PROSE_PATTERN, "-i", "--exclude-dir=.venv", *includes)

    assert [line for line in found if not exempt(line, SOURCE_FILE, *EXEMPT_IN_PACK)] == []


def test_leg_2_no_legacy_prose_in_a_project(term: Project) -> None:
    """`LEG-2` on `TERM`: old vocabulary in documents that agents read."""
    includes = tuple(f"--include={suffix}" for suffix in PROSE_SUFFIXES)
    found = grep(term.path, PROSE_PATTERN, "-i", "--exclude-dir=.venv", *includes)

    assert [line for line in found if not exempt(line, SOURCE_FILE)] == []


@pytest.mark.parametrize("legacy", LEGACY_PATHS)
def test_leg_3_no_legacy_path_survives(root: Path, term: Project, legacy: str) -> None:
    """`LEG-3`: a deleted subsystem left on disk, in either tree."""
    assert not (root / legacy).exists()
    assert not (term.path / legacy).exists()


def test_leg_3_no_generated_directory_under_a_package(root: Path, term: Project) -> None:
    """`LEG-3`: the derived index directory of the deleted control plane."""
    assert list((root / "src").glob(f"*/{GENERATED_PACKAGE_DIRECTORY}")) == []
    assert list((term.path / "src").glob(f"*/{GENERATED_PACKAGE_DIRECTORY}")) == []


def test_leg_4_the_gate_is_exactly_twelve_hooks(root: Path, term: Project) -> None:
    """`LEG-4`: Code C, which catches a dropped hook and the eleven-hook regression."""
    assert gate_hook_ids(root) == TWELVE_HOOKS
    assert gate_hook_ids(term.path) == TWELVE_HOOKS


def test_leg_5_the_pack_is_green(root: Path) -> None:
    """`LEG-5` on `ROOT`: any regression the gate itself can see."""
    outcome = gate(root)

    assert failing_hooks(root, outcome) == frozenset(), outcome.text


def test_leg_5_a_project_is_green(term: Project) -> None:
    """`LEG-5` on `TERM`: the same gate, with no role-dependent branch."""
    outcome = gate(term.path)

    assert failing_hooks(term.path, outcome) == frozenset(), outcome.text


def test_leg_6_the_gate_definition_is_name_blind(term: Project, term2: Project) -> None:
    """`LEG-6`: a gate a pack update could not replace would carry an identity."""
    first = (term.path / "pack/configs/prek.toml").read_bytes()
    second = (term2.path / "pack/configs/prek.toml").read_bytes()

    assert first == second
