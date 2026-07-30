"""Pure compilation of declarations into canonical derived-index values."""

from dataclasses import dataclass
from hashlib import sha256
import json
import keyword
from typing import Literal

import icontract

from repoctl.modules.repository_generation.domain.intents import (
    CapabilityDeclaration,
    RepositoryPath,
)
from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipZone,
    OwnershipZoneRoots,
    RepositoryPathCandidate,
    classify_path,
)
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


type DerivedWrite = tuple[RepositoryPath, str]
type ImportBinding = tuple[str, str, str]
type ActiveModule = tuple[DerivedCapability, str]
type ProofCatalogOwnership = Literal["foundation", "product"]


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivedCompilation:
    """The complete deterministic projection of one declaration set."""

    source_state_sha256: str
    writes: tuple[DerivedWrite, ...]


class DerivedIndexRenderingError(ValueError):
    """Raised when a declaration cannot safely produce explicit Python source."""


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


def _canonical_declarations(
    declarations: tuple[CapabilityDeclaration, ...],
) -> tuple[CapabilityDeclaration, ...]:
    return tuple(sorted(declarations, key=_declaration_facts))


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
            for declaration in _canonical_declarations(declarations)
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


def _source_state_sha256(
    declarations: tuple[CapabilityDeclaration, ...],
) -> str:
    digest = sha256()
    for declaration in _canonical_declarations(declarations):
        _ = digest.update(f".repo/capabilities/{declaration.name}.toml".encode())
        _ = digest.update(b"\0")
        _ = digest.update(declaration.canonical_document().encode("utf-8"))
        _ = digest.update(b"\0")
    return digest.hexdigest()


def _python_index_content(
    *,
    source_state_sha256: str,
    variable: str,
    elements: tuple[str, ...],
    imports: tuple[str, ...] = (),
    value_type: str = "str",
) -> str:
    rendered_elements = "".join(f"    {element},\n" for element in elements)
    tuple_value = f"(\n{rendered_elements})" if elements else "()"
    import_block = "\n".join(imports)
    prefix = f"{import_block}\n\n" if import_block else ""
    return (
        "# Generated from repository declarations. DO NOT EDIT.\n"
        f"# source-state-sha256: {source_state_sha256}\n\n"
        f"{prefix}{variable}: tuple[{value_type}, ...] = {tuple_value}\n"
    )


def _is_identifier(value: str) -> bool:
    return value.isidentifier() and not keyword.iskeyword(value)


def _is_dotted_identifier(value: str) -> bool:
    return all(_is_identifier(segment) for segment in value.split("."))


def _configured_capability_module(
    *,
    package: str,
    name: str,
    value: str,
    approved_system_modules: tuple[tuple[str, str], ...],
) -> str:
    product_module = f"{package}.modules.{name}"
    configured_system_module = next(
        (module for configured_name, module in approved_system_modules if configured_name == name),
        None,
    )
    if value not in {product_module, configured_system_module}:
        raise DerivedIndexRenderingError(
            "Declared capability module is not the configured product or system capability: "
            + repr(value)
        )
    return value


def _configured_active_modules(
    *,
    package: str,
    active: tuple[DerivedCapability, ...],
    approved_system_modules: tuple[tuple[str, str], ...],
) -> tuple[ActiveModule, ...]:
    return tuple(
        (
            entry,
            _configured_capability_module(
                package=package,
                name=entry.name,
                value=entry.python_module,
                approved_system_modules=approved_system_modules,
            ),
        )
        for entry in active
    )


def _import_binding(
    *,
    reference: str,
    alias: str,
    capability_module: str,
) -> ImportBinding:
    module, separator, member = reference.rpartition(":")
    if separator != ":" or not _is_dotted_identifier(module) or not _is_identifier(member):
        raise DerivedIndexRenderingError(
            f"Declared activation reference cannot be rendered as an import: {reference!r}"
        )
    if module != capability_module and not module.startswith(f"{capability_module}."):
        raise DerivedIndexRenderingError(
            f"Declared activation reference escapes its capability module: {reference!r}"
        )
    return (module, member, alias)


def _import_index_content(
    *,
    source_state_sha256: str,
    variable: str,
    bindings: tuple[ImportBinding, ...],
) -> str:
    return _python_index_content(
        source_state_sha256=source_state_sha256,
        variable=variable,
        elements=tuple(alias for _, _, alias in bindings),
        imports=tuple(
            f"from {module} import {member} as {alias}" for module, member, alias in bindings
        ),
        value_type="object",
    )


def _proof_catalog_ownership(
    path: RepositoryPath,
    ownership_zones: tuple[OwnershipZoneRoots, ...],
) -> ProofCatalogOwnership:
    zone = classify_path(
        RepositoryPathCandidate(value=path.value),
        ownership_zones,
    )
    if zone == OwnershipZone("FOUNDATION"):
        return "foundation"
    if zone == OwnershipZone("PRODUCT"):
        return "product"
    raise DerivedIndexRenderingError(
        f"Declared proof catalog is not FOUNDATION or PRODUCT owned: {path.value!r}"
    )


def _proof_catalog_reference(
    path: RepositoryPath,
    ownership_zones: tuple[OwnershipZoneRoots, ...],
) -> dict[str, str]:
    return {
        "path": path.value,
        "ownership_zone": _proof_catalog_ownership(path, ownership_zones),
    }


def _proof_index_content(
    *,
    source_state_sha256: str,
    active: tuple[DerivedCapability, ...],
    ownership_zones: tuple[OwnershipZoneRoots, ...],
) -> str:
    return json.dumps(
        {
            "_generated": "Generated from repository declarations. DO NOT EDIT.",
            "source_state_sha256": source_state_sha256,
            "schema_version": 1,
            "catalogs": [
                _proof_catalog_reference(
                    RepositoryPath(value=entry.proof_catalog),
                    ownership_zones,
                )
                for entry in active
            ],
        },
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
    )


def _proof_index_write(
    source_state_sha256: str,
    active: tuple[DerivedCapability, ...],
    ownership_zones: tuple[OwnershipZoneRoots, ...],
) -> DerivedWrite:
    return (
        RepositoryPath(value="proof/_generated/index.json"),
        _proof_index_content(
            source_state_sha256=source_state_sha256,
            active=active,
            ownership_zones=ownership_zones,
        )
        + "\n",
    )


def _derived_writes(
    package: str,
    source_state_sha256: str,
    active: tuple[DerivedCapability, ...],
    ownership_zones: tuple[OwnershipZoneRoots, ...],
    approved_system_modules: tuple[tuple[str, str], ...],
) -> tuple[DerivedWrite, ...]:
    prefix = f"src/{package}/_generated"
    active_modules = _configured_active_modules(
        package=package,
        active=active,
        approved_system_modules=approved_system_modules,
    )
    composition_bindings = tuple(
        _import_binding(
            reference=entry.factory,
            alias=f"build_{entry.name}",
            capability_module=module,
        )
        for entry, module in active_modules
        if entry.factory
    )
    cli_catalog_bindings = tuple(
        _import_binding(
            reference=entry.cli_catalog,
            alias=f"commands_{entry.name}",
            capability_module=module,
        )
        for entry, module in active_modules
        if entry.cli_catalog
    )
    return (
        (
            RepositoryPath(value=f"{prefix}/active_capabilities.py"),
            _python_index_content(
                source_state_sha256=source_state_sha256,
                variable="ACTIVE_CAPABILITIES",
                elements=tuple(
                    json.dumps(module, ensure_ascii=False) for _, module in active_modules
                ),
            ),
        ),
        (
            RepositoryPath(value=f"{prefix}/composition.py"),
            _import_index_content(
                source_state_sha256=source_state_sha256,
                variable="COMPOSITION",
                bindings=composition_bindings,
            ),
        ),
        (
            RepositoryPath(value=f"{prefix}/cli_catalog.py"),
            _import_index_content(
                source_state_sha256=source_state_sha256,
                variable="CLI_CATALOGS",
                bindings=cli_catalog_bindings,
            ),
        ),
        _proof_index_write(source_state_sha256, active, ownership_zones),
    )


def render_derived_indexes(
    *,
    package: str,
    declarations: tuple[CapabilityDeclaration, ...],
    ownership_zones: tuple[OwnershipZoneRoots, ...],
    approved_system_modules: tuple[tuple[str, str], ...],
) -> DerivedCompilation:
    """Render all derived projections from one explicit declaration set."""
    canonical_declarations = _canonical_declarations(declarations)
    source_state_sha256 = _source_state_sha256(canonical_declarations)
    active = compile_indexes(canonical_declarations).active
    return DerivedCompilation(
        source_state_sha256=source_state_sha256,
        writes=_derived_writes(
            package=package,
            source_state_sha256=source_state_sha256,
            active=active,
            ownership_zones=ownership_zones,
            approved_system_modules=approved_system_modules,
        ),
    )
