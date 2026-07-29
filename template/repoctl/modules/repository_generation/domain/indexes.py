"""Pure compilation of declarations into canonical derived-index values."""

from dataclasses import dataclass
import json

import icontract

from repoctl.modules.repository_generation.domain.intents import CapabilityDeclaration
from repoctl.modules.repository_generation.domain.specifications import (
    DeclarationIndexFacts,
    DerivedIndexFacts,
    derived_indexes_are_exact,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivedCapability:
    """The declaration fields used by runtime, proof, composition, and CLI indexes."""

    name: str
    python_module: str
    proof_catalog: str
    inbound: tuple[str, ...]
    outbound: tuple[str, ...]
    api: str
    factory: str
    cli_catalog: str


def _entry_facts(entry: DerivedCapability) -> DerivedIndexFacts:
    return (
        entry.name,
        entry.python_module,
        entry.proof_catalog,
        entry.inbound,
        entry.outbound,
        entry.api,
        entry.factory,
        entry.cli_catalog,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivedIndexes:
    """Canonical active capability records shared by every derived projection."""

    active: tuple[DerivedCapability, ...]

    def __post_init__(self) -> None:
        canonical = tuple(sorted(set(self.active), key=_entry_facts))
        object.__setattr__(self, "active", canonical)


def _declaration_facts(
    declaration: CapabilityDeclaration,
) -> DeclarationIndexFacts:
    return (
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


def _derived_capability(declaration: CapabilityDeclaration) -> DerivedCapability:
    return DerivedCapability(
        name=declaration.name,
        python_module=declaration.python_module,
        proof_catalog=declaration.proof_catalog,
        inbound=declaration.inbound,
        outbound=declaration.outbound,
        api=declaration.api,
        factory=declaration.factory,
        cli_catalog=declaration.cli_catalog,
    )


def _compiled_indexes_are_exact(
    declarations: tuple[CapabilityDeclaration, ...],
    result: DerivedIndexes,
) -> bool:
    return derived_indexes_are_exact(
        tuple(_declaration_facts(declaration) for declaration in declarations),
        tuple(_entry_facts(entry) for entry in result.active),
    )


@icontract.ensure(
    _compiled_indexes_are_exact,
    description="PROPERTY[REPOCTL::DERIVED-INDEX-EXACT]",
)
def compile_indexes(
    declarations: tuple[CapabilityDeclaration, ...],
) -> DerivedIndexes:
    """Project only explicitly supplied active declarations in canonical order."""
    return DerivedIndexes(
        active=tuple(
            _derived_capability(declaration)
            for declaration in declarations
            if declaration.status == "active"
        )
    )


def canonical_index_bytes(indexes: DerivedIndexes) -> bytes:
    """Serialize a compiled index with stable UTF-8 JSON bytes."""
    payload = {
        "schema_version": 1,
        "active": [
            {
                "name": entry.name,
                "python_module": entry.python_module,
                "proof_catalog": entry.proof_catalog,
                "inbound": list(entry.inbound),
                "outbound": list(entry.outbound),
                "api": entry.api,
                "factory": entry.factory,
                "cli_catalog": entry.cli_catalog,
            }
            for entry in indexes.active
        ],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
