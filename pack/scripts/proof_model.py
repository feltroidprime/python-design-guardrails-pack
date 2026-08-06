"""Shared immutable models for the proof-contract static analysis.

This is machinery for every other `proof_*.py` module. It emits no PROOF
code.
"""

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

Definition = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
FunctionDefinition = ast.FunctionDef | ast.AsyncFunctionDef
BindingKey = tuple[str, str, str]


class DiscoveryError(ValueError):
    """Raised when proof metadata uses a dynamic or ambiguous form."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ContractLink:
    path: Path
    line: int
    decorator: str
    property_id: str | None
    description: str | None
    invoked_targets: frozenset[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceTarget:
    path: Path
    line: int
    target: str
    kind: str
    contracts: tuple[ContractLink, ...]

    @property
    def property_ids(self) -> frozenset[str]:
        return frozenset(
            contract.property_id for contract in self.contracts if contract.property_id is not None
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OracleShape:
    path: Path
    line: int
    target: str
    module_stem: str
    is_async: bool
    return_annotation: str
    has_variadic_parameters: bool
    called_names: frozenset[str]
    imported_modules: frozenset[str]
    forbidden_nodes: frozenset[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class ProofTest:
    path: Path
    line: int
    name: str
    proves_ids: tuple[str, ...]
    falsifies_ids: tuple[str, ...]
    uses_hypothesis: bool
    uses_state_machine: bool
    has_assertion: bool
    called_names: frozenset[str]
    invoked_targets: frozenset[str]
    helper_names: frozenset[str]
    helper_property_ids: tuple[str, ...]
    dynamic_helper_calls: tuple[str, ...]
    state_machine_invoked_targets: frozenset[str]
    state_machine_helper_names: frozenset[str]
    state_machine_helper_property_ids: tuple[str, ...]
    state_machine_has_assertion: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class StateMachineFacts:
    invoked_targets: frozenset[str]
    helper_names: frozenset[str]
    helper_property_ids: tuple[str, ...]
    has_assertion: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ModuleImport:
    module: str
    prefix: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportBindings:
    symbols: dict[str, str]
    modules: tuple[ModuleImport, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope:
    key: str
    node: ast.Module | FunctionDefinition
    class_key: str | None
    receiver_name: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class OriginExpression:
    direct_target: str | None = None
    reference: BindingKey = ("", "", "")
    unknown: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class InvocationIndex:
    by_node: dict[int, frozenset[str]]
    module_targets: frozenset[str]


@dataclass(frozen=True, slots=True)
class AssignmentRecord:
    keys: tuple[BindingKey, ...]
    expression: OriginExpression
