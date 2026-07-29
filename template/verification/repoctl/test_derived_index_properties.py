"""Properties for the pure repository derived-index compiler."""

import ast
import inspect
from pathlib import Path

from hypothesis import given, strategies as st
import pytest

from repoctl.modules.repository_generation.api import (
    CapabilityDeclaration,
    CapabilityStatus,
    DeclarationIndexFacts,
    DerivedCapability,
    DerivedIndexes,
    DerivedIndexFacts,
    canonical_index_bytes,
    compile_indexes,
    derived_indexes_are_exact,
)
from verification.harness.assertions import assert_falsifies, assert_property

STATUSES: tuple[CapabilityStatus, ...] = ("draft", "active", "retired")


def _declaration(index: int, status: CapabilityStatus) -> CapabilityDeclaration:
    name = f"capability_{index}"
    module = f"example.modules.{name}"
    return CapabilityDeclaration(
        name=name,
        python_module=module,
        status=status,
        proof_catalog=f"proof/modules/{name}.toml",
        inbound=("python",),
        outbound=(),
        api=f"{module}.api",
        factory=f"{module}.bootstrap:build" if index % 2 else "",
        cli_catalog=f"{module}.adapters.inbound.cli_catalog:COMMANDS" if index % 3 else "",
    )


def _declaration_facts(
    declarations: tuple[CapabilityDeclaration, ...],
) -> tuple[DeclarationIndexFacts, ...]:
    return tuple(
        (
            declaration.name,
            declaration.status,
            declaration.python_module,
            declaration.proof_catalog,
            declaration.inbound,
            declaration.outbound,
            declaration.api,
            declaration.factory,
            declaration.cli_catalog,
        )
        for declaration in declarations
    )


def _index_facts(indexes: DerivedIndexes) -> tuple[DerivedIndexFacts, ...]:
    return tuple(
        (
            entry.name,
            entry.python_module,
            entry.proof_catalog,
            entry.inbound,
            entry.outbound,
            entry.api,
            entry.factory,
            entry.cli_catalog,
        )
        for entry in indexes.active
    )


@pytest.mark.proof
@pytest.mark.proves("REPOCTL::DERIVED-INDEX-EXACT")
@given(extra_statuses=st.lists(st.sampled_from(STATUSES), max_size=97))
def test_compiled_membership_is_exactly_the_active_subset(
    extra_statuses: list[CapabilityStatus],
) -> None:
    statuses = (*STATUSES, *extra_statuses)
    declarations = tuple(_declaration(index, status) for index, status in enumerate(statuses))

    result = compile_indexes(declarations)

    assert_property(
        condition=derived_indexes_are_exact(
            _declaration_facts(declarations),
            _index_facts(result),
        ),
        property_id="REPOCTL::DERIVED-INDEX-EXACT",
    )
    names = tuple(entry.name for entry in result.active)
    expected_names = {
        declaration.name for declaration in declarations if declaration.status == "active"
    }
    assert set(names) == expected_names
    assert len(names) == len(set(names))


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::DERIVED-INDEX-EXACT")
def test_a_draft_entry_is_a_real_index_counterexample() -> None:
    declaration = _declaration(0, "draft")
    undeclared_entry = DerivedCapability(
        name=declaration.name,
        python_module=declaration.python_module,
        proof_catalog=declaration.proof_catalog,
        inbound=declaration.inbound,
        outbound=declaration.outbound,
        api=declaration.api,
        factory=declaration.factory,
        cli_catalog=declaration.cli_catalog,
    )
    assert_falsifies(
        condition=derived_indexes_are_exact(
            _declaration_facts((declaration,)),
            _index_facts(DerivedIndexes(active=(undeclared_entry,))),
        ),
        property_id="REPOCTL::DERIVED-INDEX-EXACT",
    )


@given(extra_statuses=st.lists(st.sampled_from(STATUSES), max_size=97))
def test_compilation_is_byte_stable_for_the_same_declaration_set(
    extra_statuses: list[CapabilityStatus],
) -> None:
    statuses = (*STATUSES, *extra_statuses)
    declarations = tuple(_declaration(index, status) for index, status in enumerate(statuses))

    first = canonical_index_bytes(compile_indexes(declarations))
    second = canonical_index_bytes(compile_indexes(tuple(reversed(declarations))))

    assert first == second


def test_compiler_cannot_perform_runtime_module_discovery() -> None:
    source_path = inspect.getsourcefile(compile_indexes)
    assert source_path is not None
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    imported = {
        module
        for node in ast.walk(tree)
        for module in (
            tuple(alias.name for alias in node.names)
            if isinstance(node, ast.Import)
            else ((node.module or ""),)
            if isinstance(node, ast.ImportFrom)
            else ()
        )
    }
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }

    assert all(
        module != forbidden and not module.startswith(f"{forbidden}.")
        for module in imported
        for forbidden in ("importlib", "pkgutil")
    )
    assert "__import__" not in called
