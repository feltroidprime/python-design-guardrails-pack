"""Public loader for the repository's policy-led proof catalog tree.

The proof surface is pack-owned. Its policy and its catalogs live under
`pack/proof/`, and every path in this module is resolved from the repository
root, never from the pack root.
"""

from pathlib import Path

from scripts.architecture_policy import PACK_DIRECTORY, SOURCE_DIRECTORY, derive_package
from scripts.proof_catalog_model import (
    ALLOWED_OWNERSHIP_ZONES,
    CATALOG_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    CatalogEntry,
    CatalogError,
    CatalogIndexEntry,
    CatalogLocation,
    CatalogOwnershipError,
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
    text,
)

POLICY_RELATIVE = Path(PACK_DIRECTORY) / "proof" / "policy.toml"

__all__ = [
    "CatalogEntry",
    "CatalogError",
    "CatalogIndexEntry",
    "CatalogLocation",
    "CatalogOwnershipError",
    "DuplicatePropertyIdError",
    "ProofCatalog",
    "ProofCatalogIndex",
    "ProofExemption",
    "ProofPolicy",
    "PropertySpec",
    "load_catalog",
]


def _validate_catalog_ownership(catalogs: tuple[CatalogEntry, ...]) -> None:
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


def _discover_catalogs(proof_root: Path, policy: ProofPolicy) -> tuple[tuple[Path, str], ...]:
    discovered: list[tuple[Path, str]] = []
    for location in policy.catalog_locations:
        entry = proof_root / location.relative_path
        if location.relative_path.suffix == ".toml":
            if not entry.is_file():
                raise CatalogError(f"Catalog '{entry.as_posix()}' does not exist")
            discovered.append((entry, location.ownership_zone))
            continue
        if not entry.exists():
            continue
        if not entry.is_dir():
            raise CatalogError(f"Catalog root '{entry.as_posix()}' must be a directory")
        discovered.extend(
            (candidate, location.ownership_zone)
            for candidate in sorted(entry.rglob("*.toml"))
            if candidate.is_file()
        )
    if not discovered:
        raise CatalogError("proof policy declares no catalog files")
    return tuple(sorted(discovered, key=lambda item: item[0].as_posix()))


def _load_catalog_entry(entry: Path, ownership_zone: str) -> CatalogEntry:
    raw = read_toml(entry, "proof catalog")
    if raw.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogError(
            f"Catalog '{entry.as_posix()}' schema_version must be exactly {CATALOG_SCHEMA_VERSION}"
        )
    declared_zone = text(
        raw.get("ownership_zone"),
        f"Catalog '{entry.as_posix()}'.ownership_zone",
    )
    if declared_zone not in ALLOWED_OWNERSHIP_ZONES:
        raise CatalogOwnershipError(
            f"Catalog '{entry.as_posix()}' has unsupported ownership zone '{declared_zone}'"
        )
    if declared_zone != ownership_zone:
        raise CatalogOwnershipError(
            " ".join(
                (
                    f"Catalog '{entry.as_posix()}' declares ownership zone '{declared_zone}',",
                    f"but its path belongs to '{ownership_zone}'",
                )
            )
        )
    return CatalogEntry(
        path=entry,
        ownership_zone=declared_zone,
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
    policy = load_policy(root, derive_package(root / SOURCE_DIRECTORY), raw)
    catalogs = tuple(
        _load_catalog_entry(entry, ownership_zone)
        for entry, ownership_zone in _discover_catalogs(policy_location.parent, policy)
    )
    _validate_catalog_ownership(catalogs)
    return ProofCatalog(
        path=policy_location,
        policy=policy,
        catalogs=catalogs,
        properties=tuple(
            property_spec for catalog in catalogs for property_spec in catalog.properties
        ),
        exemptions=tuple(exemption for catalog in catalogs for exemption in catalog.exemptions),
    )
