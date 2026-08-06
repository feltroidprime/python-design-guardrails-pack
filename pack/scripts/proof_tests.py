"""Discover canonical property proofs and falsifying canaries.

This is machinery for `proof_evidence_rules.py`. It emits no PROOF code.
"""

import ast
from typing import TYPE_CHECKING

from scripts.proof_assertions import helper_calls
from scripts.proof_ast import dotted_name
from scripts.proof_invocations import invocation_index
from scripts.proof_model import (
    DiscoveryError,
    FunctionDefinition,
    InvocationIndex,
    ProofTest,
)
from scripts.proof_reexports import resolve_reexported_target
from scripts.proof_stateful import state_machine_facts

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def _marker_ids(decorators: Iterable[ast.expr], marker: str, path: Path) -> tuple[str, ...]:
    matches = tuple(
        decorator
        for decorator in decorators
        if isinstance(decorator, ast.Call)
        and dotted_name(decorator.func).endswith(f"pytest.mark.{marker}")
    )
    if len(matches) > 1:
        raise DiscoveryError(f"{path}:{matches[1].lineno}: duplicate @{marker} marker")
    if not matches:
        return ()
    call = matches[0]
    if call.keywords or len(call.args) != 1:
        raise DiscoveryError(
            f"{path}:{call.lineno}: @{marker} requires exactly one literal property ID"
        )
    argument = call.args[0]
    if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
        raise DiscoveryError(f"{path}:{call.lineno}: @{marker} ID must be a string literal")
    return (argument.value,)


def _uses_given(node: FunctionDefinition) -> bool:
    return any(
        isinstance(decorator, ast.Call) and dotted_name(decorator.func).split(".")[-1] == "given"
        for decorator in node.decorator_list
    )


def _proof_test(
    node: FunctionDefinition,
    path: Path,
    tree: ast.Module,
    invocation_index: InvocationIndex,
) -> ProofTest | None:
    proves_ids = _marker_ids(node.decorator_list, "proves", path)
    falsifies_ids = _marker_ids(node.decorator_list, "falsifies", path)
    if not proves_ids and not falsifies_ids:
        return None
    helpers, helper_ids, dynamic = helper_calls(node)
    if dynamic:
        message = (
            f"{path}:{node.lineno}: proof helper calls require one literal property_id: "
            f"{', '.join(dynamic)}"
        )
        raise DiscoveryError(message)
    call_names = {
        dotted_name(candidate.func).split(".")[-1]
        for candidate in ast.walk(node)
        if isinstance(candidate, ast.Call)
    }
    stateful_facts = state_machine_facts(node, tree, path, invocation_index)
    return ProofTest(
        path=path,
        line=node.lineno,
        name=node.name,
        proves_ids=proves_ids,
        falsifies_ids=falsifies_ids,
        uses_hypothesis=_uses_given(node),
        uses_state_machine="run_state_machine_as_test" in call_names,
        has_assertion=any(
            isinstance(candidate, (ast.Assert, ast.Raise)) for candidate in ast.walk(node)
        )
        or bool(helpers),
        called_names=frozenset(call_names),
        invoked_targets=invocation_index.by_node.get(id(node), frozenset()),
        helper_names=helpers,
        helper_property_ids=helper_ids,
        dynamic_helper_calls=dynamic,
        state_machine_invoked_targets=stateful_facts.invoked_targets,
        state_machine_helper_names=stateful_facts.helper_names,
        state_machine_helper_property_ids=stateful_facts.helper_property_ids,
        state_machine_has_assertion=stateful_facts.has_assertion,
    )


def _normalize_invocations(
    index: InvocationIndex,
    source_roots: tuple[Path, ...],
) -> InvocationIndex:
    def normalized(targets: frozenset[str]) -> frozenset[str]:
        return frozenset(resolve_reexported_target(source_roots, target) for target in targets)

    by_node = {node_id: normalized(targets) for node_id, targets in index.by_node.items()}
    return InvocationIndex(
        by_node=by_node,
        module_targets=frozenset(target for targets in by_node.values() for target in targets),
    )


def _tests_in_file(
    path: Path,
    source_roots: tuple[Path, ...],
) -> tuple[ProofTest, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    index = _normalize_invocations(invocation_index(tree), source_roots)
    tests: list[ProofTest] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        proof_test = _proof_test(node, path, tree, index)
        if proof_test is not None:
            tests.append(proof_test)
    return tuple(tests)


def discover_tests(
    test_root: Path,
    *,
    source_roots: tuple[Path, ...] = (),
) -> tuple[ProofTest, ...]:
    if not test_root.is_dir():
        raise DiscoveryError(f"Proof test root does not exist: {test_root}")
    return tuple(
        test
        for path in sorted(test_root.rglob("*.py"))
        for test in _tests_in_file(path, source_roots)
    )
