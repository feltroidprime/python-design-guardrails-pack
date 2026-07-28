"""Immutable models and stable wire shape for the multi-catalog proof surface."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

POLICY_SCHEMA_VERSION = 2
CATALOG_SCHEMA_VERSION = 1
CATALOG_INDEX_SCHEMA_VERSION = 1
ALLOWED_OWNERSHIP_ZONES = frozenset({"foundation", "product"})


class CatalogError(ValueError):
    """Raised when the proof policy or one of its catalogs is invalid."""


class DuplicatePropertyIdError(CatalogError):
    """Raised when more than one catalog declares the same property ID."""


class CatalogOwnershipError(CatalogError):
    """Raised when a catalog's declared ownership zone disagrees with its path."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogLocation:
    ownership_zone: str
    relative_path: Path


@dataclass(frozen=True, slots=True, kw_only=True)
class ProofPolicy:
    source_roots: tuple[Path, ...]
    test_roots: tuple[Path, ...]
    behavior_roots: tuple[str, ...]
    excluded_module_stems: frozenset[str]
    oracle_module_stems: frozenset[str]
    catalog_locations: tuple[CatalogLocation, ...]

    @property
    def source_root(self) -> tuple[Path, ...]:
        """Compatibility facade for discovery helpers that accept one or many roots."""
        return self.source_roots


@dataclass(frozen=True, slots=True, kw_only=True)
class PropertySpec:
    property_id: str
    title: str
    statement: str
    scope: str
    assumptions: tuple[str, ...]
    kind: str
    strength: str
    targets: tuple[str, ...]
    oracles: tuple[str, ...]
    evidence: frozenset[str]
    counterexample: str
    failure_modes: tuple[str, ...]
    crosshair_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ProofExemption:
    target: str
    reason: str
    revisit: date


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogEntry:
    path: Path
    ownership_zone: str
    properties: tuple[PropertySpec, ...]
    exemptions: tuple[ProofExemption, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogIndexEntry:
    location: str
    ownership_zone: str
    property_ids: tuple[str, ...]
    exemption_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ProofCatalogIndex:
    """Stable, JSON-ready aggregation for a future generated proof index."""

    schema_version: int
    catalogs: tuple[CatalogIndexEntry, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "catalogs": [
                {
                    "path": entry.location,
                    "ownership_zone": entry.ownership_zone,
                    "property_ids": list(entry.property_ids),
                    "exemption_targets": list(entry.exemption_targets),
                }
                for entry in self.catalogs
            ],
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ProofCatalog:
    path: Path
    policy: ProofPolicy
    catalogs: tuple[CatalogEntry, ...]
    properties: tuple[PropertySpec, ...]
    exemptions: tuple[ProofExemption, ...]

    @property
    def by_id(self) -> dict[str, PropertySpec]:
        return {property_spec.property_id: property_spec for property_spec in self.properties}

    @property
    def target_ids(self) -> dict[str, frozenset[str]]:
        result: dict[str, set[str]] = {}
        for property_spec in self.properties:
            for target in property_spec.targets:
                result.setdefault(target, set()).add(property_spec.property_id)
        return {target: frozenset(ids) for target, ids in result.items()}

    @property
    def index(self) -> ProofCatalogIndex:
        root = self.path.parent.parent
        return ProofCatalogIndex(
            schema_version=CATALOG_INDEX_SCHEMA_VERSION,
            catalogs=tuple(
                CatalogIndexEntry(
                    location=entry.path.relative_to(root).as_posix(),
                    ownership_zone=entry.ownership_zone,
                    property_ids=tuple(
                        property_spec.property_id for property_spec in entry.properties
                    ),
                    exemption_targets=tuple(exemption.target for exemption in entry.exemptions),
                )
                for entry in self.catalogs
            ),
        )
