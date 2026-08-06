"""Public loader for the repository's policy-led proof catalog tree.

The proof surface is pack-owned. The policy and the pack catalogs live under
`pack/proof/`, and every path in this module is resolved from the repository
root, never from the pack root.

Catalog discovery is structural, so the policy holds no catalog root and no
ownership zone. Two locations carry a catalog:

* every `*.toml` below `pack/proof/`, this policy apart.
* the `proof.toml` of each capability. AGENTS.md requires one per capability.

A capability with no `proof.toml` is a violation, and the loader reports it
by raising `CatalogError`. This module emits no `PROOF` code itself.
`proof_guard.py` turns any `CatalogError` it raises into `PROOF000`.
"""

from pathlib import Path

from scripts.architecture_policy import PACK_DIRECTORY, SOURCE_DIRECTORY, derive_package
from scripts.identity import discover_capabilities
from scripts.proof_catalog_model import (
    CATALOG_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    CatalogEntry,
    CatalogError,
    CatalogIndexEntry,
    DuplicatePropertyIdError,
    ProofCatalog,
    ProofCatalogIndex,
    ProofExemption,
    ProofPolicy,
    PropertySpec,
)
from scripts.proof_catalog_schema import (
    duplicates,
    load_exemption,
    load_policy,
    load_property,
    read_toml,
    table_array,
)

POLICY_RELATIVE = Path(PACK_DIRECTORY) / "proof" / "policy.toml"
POLICY_NAME = "policy.toml"
CAPABILITY_CATALOG_NAME = "proof.toml"

__all__ = [
    "CatalogEntry",
    "CatalogError",
    "CatalogIndexEntry",
    "DuplicatePropertyIdError",
    "ProofCatalog",
    "ProofCatalogIndex",
    "ProofExemption",
    "ProofPolicy",
    "PropertySpec",
    "load_catalog",
]


def _validate_catalog_properties(catalogs: tuple[CatalogEntry, ...]) -> None:
    locations_by_property: dict[str, list[Path]] = {}
    for catalog in catalogs:
        for property_spec in catalog.properties:
            locations_by_property.setdefault(property_spec.property_id, []).append(catalog.path)
    duplicated = {
        property_id: locations
        for property_id, locations in locations_by_property.items()
        if len(locations) > 1
    }
    if duplicated:
        descriptions = ", ".join(
            f"{property_id} ({', '.join(location.as_posix() for location in locations)})"
            for property_id, locations in sorted(duplicated.items())
        )
        raise DuplicatePropertyIdError(f"Duplicate property IDs across catalogs: {descriptions}")
    exemptions = tuple(exemption for catalog in catalogs for exemption in catalog.exemptions)
    exemption_targets = tuple(item.target for item in exemptions)
    if duplicates(exemption_targets):
        raise CatalogError("Proof catalogs repeat an exempted target")
    proven_targets = {
        target
        for catalog in catalogs
        for property_spec in catalog.properties
        for target in property_spec.targets
    }
    overlap = sorted(set(exemption_targets) & proven_targets)
    if overlap:
        raise CatalogError(f"Targets cannot be both proven and exempted: {', '.join(overlap)}")


def _pack_catalogs(proof_root: Path) -> tuple[Path, ...]:
    """Every `*.toml` below `pack/proof/`, the policy apart."""
    return tuple(
        sorted(
            candidate
            for candidate in proof_root.rglob("*.toml")
            if candidate.is_file() and candidate.name != POLICY_NAME
        )
    )


def _capability_catalogs(
    root: Path, package: str, capabilities: tuple[str, ...]
) -> tuple[Path, ...]:
    """The `proof.toml` of each capability. AGENTS.md requires one per capability."""
    package_root = root / SOURCE_DIRECTORY / package
    catalogs: list[Path] = []
    missing: list[str] = []
    for capability in capabilities:
        catalog = package_root / capability / CAPABILITY_CATALOG_NAME
        if catalog.is_file():
            catalogs.append(catalog)
        else:
            missing.append(capability)
    if missing:
        raise CatalogError(
            f"Capability without {CAPABILITY_CATALOG_NAME}: {', '.join(sorted(missing))}"
        )
    return tuple(catalogs)


def _discover_catalogs(
    root: Path, proof_root: Path, package: str, capabilities: tuple[str, ...]
) -> tuple[Path, ...]:
    discovered = (
        *_pack_catalogs(proof_root),
        *_capability_catalogs(root, package, capabilities),
    )
    if not discovered:
        raise CatalogError("the proof surface holds no catalog file")
    return discovered


def _load_catalog_entry(entry: Path) -> CatalogEntry:
    raw = read_toml(entry, "proof catalog")
    if raw.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogError(
            f"Catalog '{entry.as_posix()}' schema_version must be exactly {CATALOG_SCHEMA_VERSION}"
        )
    return CatalogEntry(
        path=entry,
        properties=tuple(
            load_property(value, index)
            for index, value in enumerate(
                table_array(raw, "properties", allow_empty=True),
                start=1,
            )
        ),
        exemptions=tuple(
            load_exemption(value, index)
            for index, value in enumerate(
                table_array(raw, "exemptions", allow_empty=True),
                start=1,
            )
        ),
    )


def load_catalog(root: Path) -> ProofCatalog:
    """Load the proof surface of one repository root, from `pack/proof/`."""
    policy_location = root / POLICY_RELATIVE
    raw = read_toml(policy_location, "proof policy")
    if raw.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise CatalogError(
            f"proof/policy.toml schema_version must be exactly {POLICY_SCHEMA_VERSION}"
        )
    if "properties" in raw or "exemptions" in raw:
        raise CatalogError("proof/policy.toml must not declare properties or exemptions")
    package = derive_package(root / SOURCE_DIRECTORY)
    capabilities = discover_capabilities(root, package)
    policy = load_policy(root, package, capabilities, raw)
    catalogs = tuple(
        _load_catalog_entry(entry)
        for entry in _discover_catalogs(root, policy_location.parent, package, capabilities)
    )
    _validate_catalog_properties(catalogs)
    return ProofCatalog(
        path=policy_location,
        policy=policy,
        catalogs=catalogs,
        properties=tuple(
            property_spec for catalog in catalogs for property_spec in catalog.properties
        ),
        exemptions=tuple(exemption for catalog in catalogs for exemption in catalog.exemptions),
    )
