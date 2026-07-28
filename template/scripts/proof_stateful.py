"""Discover the reachable evidence inside a Hypothesis state machine."""

import ast
from pathlib import Path

from scripts.proof_assertions import helper_calls
from scripts.proof_ast import dotted_name, function_receiver
from scripts.proof_model import (
    DiscoveryError,
    FunctionDefinition,
    InvocationIndex,
    StateMachineFacts,
)

STATE_MACHINE_ENTRY_DECORATORS = frozenset({"initialize", "invariant", "rule"})


def _state_machine_runner_calls(test: FunctionDefinition) -> tuple[ast.Call, ...]:
    return tuple(
        candidate
        for candidate in ast.walk(test)
        if isinstance(candidate, ast.Call)
        and dotted_name(candidate.func).split(".")[-1] == "run_state_machine_as_test"
    )


def _state_machine_class_name(call: ast.Call, path: Path) -> str:
    if len(call.args) == 1 and not call.keywords and isinstance(call.args[0], ast.Name):
        return call.args[0].id
    raise DiscoveryError(
        f"{path}:{call.lineno}: run_state_machine_as_test requires one literal "
        "local state-machine class"
    )


def _local_state_machine_class(
    tree: ast.Module,
    class_name: str,
    path: Path,
    line: int,
) -> ast.ClassDef:
    candidates = tuple(
        candidate
        for candidate in tree.body
        if isinstance(candidate, ast.ClassDef) and candidate.name == class_name
    )
    if len(candidates) == 1:
        return candidates[0]
    raise DiscoveryError(
        f"{path}:{line}: state-machine class '{class_name}' must be defined "
        "exactly once in the proof module"
    )


def _inherits_state_machine(node: ast.ClassDef) -> bool:
    return any(
        dotted_name(base).split(".")[-1] == "RuleBasedStateMachine"
        for base in node.bases
    )


def _state_machine_class(
    test: FunctionDefinition,
    tree: ast.Module,
    path: Path,
) -> ast.ClassDef | None:
    runner_calls = _state_machine_runner_calls(test)
    if not runner_calls:
        return None
    if len(runner_calls) != 1:
        raise DiscoveryError(
            f"{path}:{test.lineno}: a stateful proof must call "
            "run_state_machine_as_test exactly once"
        )
    runner = runner_calls[0]
    class_name = _state_machine_class_name(runner, path)
    state_machine = _local_state_machine_class(tree, class_name, path, runner.lineno)
    if _inherits_state_machine(state_machine):
        return state_machine
    raise DiscoveryError(
        f"{path}:{state_machine.lineno}: state-machine class '{class_name}' must inherit "
        "RuleBasedStateMachine"
    )


def _state_machine_methods(
    state_machine: ast.ClassDef,
) -> dict[str, FunctionDefinition]:
    return {
        member.name: member
        for member in state_machine.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _decorator_name(decorator: ast.expr) -> str:
    expression = decorator.func if isinstance(decorator, ast.Call) else decorator
    return dotted_name(expression).split(".")[-1]


def _state_machine_entry_names(
    methods: dict[str, FunctionDefinition],
) -> set[str]:
    return {
        name
        for name, method in methods.items()
        if name == "__init__"
        or any(
            _decorator_name(decorator) in STATE_MACHINE_ENTRY_DECORATORS
            for decorator in method.decorator_list
        )
    }


def _local_method_calls(
    method: FunctionDefinition,
    method_names: frozenset[str],
) -> frozenset[str]:
    receiver = function_receiver(method)
    if receiver is None:
        return frozenset()
    return frozenset(
        candidate.func.attr
        for candidate in ast.walk(method)
        if isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Attribute)
        and isinstance(candidate.func.value, ast.Name)
        and candidate.func.value.id == receiver
        and candidate.func.attr in method_names
    )


def _reachable_method_names(
    methods: dict[str, FunctionDefinition],
    entry_names: set[str],
) -> frozenset[str]:
    selected = set(entry_names)
    pending = list(entry_names)
    method_names = frozenset(methods)
    while pending:
        called = _local_method_calls(methods[pending.pop()], method_names)
        additions = called - selected
        selected.update(additions)
        pending.extend(additions)
    return frozenset(selected)


def _state_machine_method_nodes(
    state_machine: ast.ClassDef,
) -> tuple[FunctionDefinition, ...]:
    methods = _state_machine_methods(state_machine)
    reachable = _reachable_method_names(methods, _state_machine_entry_names(methods))
    return tuple(method for name, method in methods.items() if name in reachable)


def _empty_state_machine_facts() -> StateMachineFacts:
    return StateMachineFacts(
        invoked_targets=frozenset(),
        helper_names=frozenset(),
        helper_property_ids=(),
        has_assertion=False,
    )


def _state_machine_helpers(
    methods: tuple[FunctionDefinition, ...],
) -> tuple[frozenset[str], tuple[str, ...], tuple[str, ...]]:
    helper_names: set[str] = set()
    helper_ids: list[str] = []
    defects: list[str] = []
    for method in methods:
        names, property_ids, method_defects = helper_calls(method)
        helper_names.update(names)
        helper_ids.extend(property_ids)
        defects.extend(method_defects)
    return frozenset(helper_names), tuple(helper_ids), tuple(defects)


def _state_machine_invoked_targets(
    methods: tuple[FunctionDefinition, ...],
    invocation_index: InvocationIndex,
) -> frozenset[str]:
    return frozenset(
        target
        for method in methods
        for target in invocation_index.by_node.get(id(method), frozenset())
    )


def _state_machine_has_assertion(
    methods: tuple[FunctionDefinition, ...],
    helper_names: frozenset[str],
) -> bool:
    return bool(helper_names) or any(
        isinstance(candidate, (ast.Assert, ast.Raise))
        for method in methods
        for candidate in ast.walk(method)
    )


def _raise_dynamic_state_machine_helpers(
    path: Path,
    state_machine: ast.ClassDef,
    defects: tuple[str, ...],
) -> None:
    if not defects:
        return
    raise DiscoveryError(
        f"{path}:{state_machine.lineno}: state-machine proof helper calls require one "
        f"literal property_id: {', '.join(defects)}"
    )


def state_machine_facts(
    test: FunctionDefinition,
    tree: ast.Module,
    path: Path,
    invocation_index: InvocationIndex,
) -> StateMachineFacts:
    state_machine = _state_machine_class(test, tree, path)
    if state_machine is None:
        return _empty_state_machine_facts()
    methods = _state_machine_method_nodes(state_machine)
    helper_names, helper_ids, defects = _state_machine_helpers(methods)
    _raise_dynamic_state_machine_helpers(path, state_machine, defects)
    return StateMachineFacts(
        invoked_targets=_state_machine_invoked_targets(methods, invocation_index),
        helper_names=helper_names,
        helper_property_ids=helper_ids,
        has_assertion=_state_machine_has_assertion(methods, helper_names),
    )
