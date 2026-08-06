"""Valid filesystem-native capabilities, `FSC-1` to `FSC-10`.

Each deleted rule of the retired capability validator is reproved here through
one `import-linter` contract on a `DEFECT` tree, and each `DEFECT` tree is a copy
of `TERM` with one capability added and exactly one defect injected.

Every assertion reads the gate hook that owns the rule, never the whole gate.
A hook-scoped reading states which rule fired, and it cannot be satisfied or
broken by an unrelated hook of the same run.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from guardrails_pack.bootstrap.tests.acceptance import capabilities
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project
from guardrails_pack.bootstrap.tests.acceptance.harness import failing_hooks, gate, run

CONTRACTS = "import-contracts"
ARCHITECTURE = "architecture"
PROOF = "proof"
FIRST = "alpha"
SECOND = "beta"
CONTAINERS = "containers ="
FOUNDATION = "_foundation"
SEAMS = ("cli", "composition", FOUNDATION)
RESERVED_API = '''"""One capability whose surface takes a reserved parameter name."""


def report(format: str = "json") -> str:
    """Report one line."""
    return format
'''
UNDOCUMENTED_API = '''"""One capability whose public function carries no docstring."""


def report() -> str:
    return "ok"
'''
UNRENDERABLE_API = '''"""One capability whose annotation is outside the closed set."""

from collections.abc import Callable


def report(handler: Callable[[], str]) -> str:
    """Report one line."""
    return handler()
'''
DEFAULT_TRUE_API = '''"""One capability whose boolean option defaults to True."""


def report(*, verbose: bool = True) -> str:
    """Report one line."""
    return "ok" if verbose else ""
'''
CLI_CASES = (
    ("CLI001", RESERVED_API),
    ("CLI002", UNDOCUMENTED_API),
    ("CLI003", UNRENDERABLE_API),
    ("CLI004", DEFAULT_TRUE_API),
)


def with_capability(build: Callable[[str], Path], term: Project, name: str) -> Path:
    """One `DEFECT` tree that already holds one clean capability."""
    tree = build(name)
    _ = capabilities.add_capability(tree, term.tokens.package, FIRST)
    return tree


def test_fsc_1_a_missing_capability_layer_breaks_a_contract(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-1`: the first rule of the retired capability validator."""
    tree = with_capability(defect, term, "missing-layer")
    capabilities.delete_layer(tree, term.tokens.package, FIRST)

    assert CONTRACTS in failing_hooks(tree)


def test_fsc_2_an_empty_layer_counts_as_missing(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-2`: a layout rule that a clone of the validator could not carry."""
    tree = with_capability(defect, term, "empty-layer")
    capabilities.empty_layer(tree, term.tokens.package, FIRST)

    assert CONTRACTS in failing_hooks(tree)


def test_fsc_3_a_sibling_import_breaks_a_contract(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-3`: the second retired rule, now the `independence` contract."""
    tree = with_capability(defect, term, "sibling-import")
    _ = capabilities.add_capability(tree, term.tokens.package, SECOND)
    capabilities.import_a_sibling(tree, term.tokens.package, FIRST, SECOND)

    assert CONTRACTS in failing_hooks(tree)


def test_fsc_4_reaching_internals_breaks_a_contract(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-4`: the third retired rule, now the `protected` contract."""
    tree = with_capability(defect, term, "internal-reach")
    capabilities.reach_an_internal(tree, term.tokens.package, FIRST)

    assert CONTRACTS in failing_hooks(tree)


def test_fsc_5_importing_pack_code_breaks_a_contract(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-5`: layout rule 4, which bans an import of pack code from a capability."""
    tree = with_capability(defect, term, "pack-import")
    capabilities.import_pack_code(tree, term.tokens.package, FIRST)

    assert CONTRACTS in failing_hooks(tree)


def test_fsc_6_the_zero_capability_project_is_green(term: Project) -> None:
    """`FSC-6`: a wildcard container breaks wrongly on a project with no capability."""
    outcome = gate(term.path, CONTRACTS)

    assert outcome.code == 0, outcome.text


def test_fsc_7_the_shim_injects_the_discovered_list(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-7`: a wildcard regression silently disables all three capability contracts."""
    tree = with_capability(defect, term, "discovered-list")
    _ = capabilities.add_capability(tree, term.tokens.package, SECOND)

    printed = run(
        ("uv", "run", "python", "-m", "scripts.import_contracts", "--print-config"),
        tree,
        PYTHONPATH=str(tree / "pack"),
    )

    assert printed.code == 0, printed.text
    block = printed.out.partition(CONTAINERS)[2].splitlines()[1:3]
    named = [line.strip() for line in block]
    assert named == [f"{term.tokens.package}.{FIRST}", f"{term.tokens.package}.{SECOND}"]
    assert [seam for seam in SEAMS if f"{term.tokens.package}.{seam}" in named] == []


def test_fsc_8_the_proof_guard_fails_a_capability_with_no_catalog(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-8`: the presence rule that the retired validator owned."""
    tree = with_capability(defect, term, "no-proof")
    capabilities.delete_proof(tree, term.tokens.package, FIRST)

    assert PROOF in failing_hooks(tree)


def test_fsc_9_an_uncomposed_capability_is_a_fact(
    defect: Callable[[str], Path], term: Project
) -> None:
    """`FSC-9`: a gate that failed on legal work in progress would be a wall."""
    baseline = failing_hooks(term.path)
    tree = with_capability(defect, term, "uncomposed")

    assert failing_hooks(tree) <= baseline


@pytest.mark.parametrize(("rule", "api"), CLI_CASES, ids=[rule for rule, _ in CLI_CASES])
def test_fsc_10_each_command_surface_rule_fires(
    defect: Callable[[str], Path], term: Project, rule: str, api: str
) -> None:
    """`FSC-10`: `CLI001` to `CLI004`, over every `api.py`, composed or not."""
    tree = defect(f"cli-{rule.lower()}")
    _ = capabilities.add_capability(tree, term.tokens.package, FIRST, api=api)

    outcome = gate(tree, ARCHITECTURE)

    assert ARCHITECTURE in failing_hooks(tree, outcome)
    assert rule in outcome.text
