"""Schema and loader for the repository's closed property catalog."""

import re
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

POLICY_SCHEMA_VERSION = 2
CATALOG_SCHEMA_VERSION = 1
CATALOG_INDEX_SCHEMA_VERSION = 1
PROPERTY_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
TARGET_PATTERN = re.compile(r"^[a-z_][a-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")
MODULE_PATTERN = re.compile(r"^[a-z_][a-z0-9_.]*$")
ALLOWED_OWNERSHIP_ZONES = frozenset({"foundation", "product"})
ALLOWED_KINDS = frozenset(
    {
        "contract",
        "determinism",
        "idempotence",
        "invariant",
        "model",
        "preservation",
        "roundtrip",
        "state_machine",
    }
)
ALLOWED_EVIDENCE = frozenset(
    {"icontract", "hypothesis", "hypothesis-stateful", "crosshair", "falsifier"}
)
# A discovered candidate may be useful during design, but it cannot close the
# production proof surface. Agents must promote accepted laws to normative.
ALLOWED_STRENGTHS = frozenset({"normative"})


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
    path: str
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
                    "path": entry.path,
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
        return {
            property_spec.property_id: property_spec
            for property_spec in self.properties
        }

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
                    path=entry.path.relative_to(root).as_posix(),
                    ownership_zone=entry.ownership_zone,
                    property_ids=tuple(
                        property_spec.property_id for property_spec in entry.properties
                    ),
                    exemption_targets=tuple(
                        exemption.target for exemption in entry.exemptions
                    ),
                )
                for entry in self.catalogs
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class _PropertyIdentity:
    property_id: str
    kind: str
    strength: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _PropertyLinks:
    targets: tuple[str, ...]
    oracles: tuple[str, ...]
    crosshair_targets: tuple[str, ...]


def _table(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CatalogError(f"{name} must be a TOML table")
    return cast("dict[str, object]", value)


def _array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise CatalogError(f"{name} must be an array")
    return cast("list[object]", value)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{name} must be a non-blank string")
    return value.strip()


def _text_tuple(
    value: object, name: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    values = _array(value, name)
    if not values and not allow_empty:
        raise CatalogError(f"{name} must be a non-empty array of non-blank strings")
    return tuple(_text(item, f"{name} item") for item in values)


def _optional_text_tuple(value: object | None, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    return _text_tuple(value, name, allow_empty=True)


def _validate_targets(values: tuple[str, ...], name: str) -> None:
    invalid = tuple(
        value for value in values if TARGET_PATTERN.fullmatch(value) is None
    )
    if invalid:
        raise CatalogError(f"{name} contains invalid target(s): {', '.join(invalid)}")
    if len(set(values)) != len(values):
        raise CatalogError(f"{name} repeats a target")


def _validate_modules(values: tuple[str, ...], name: str) -> None:
    invalid = tuple(
        value for value in values if MODULE_PATTERN.fullmatch(value) is None
    )
    if invalid:
        raise CatalogError(f"{name} contains invalid module(s): {', '.join(invalid)}")


def _relative_path(value: str, name: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise CatalogError(f"{name} must be a repository-relative path")
    return path


def _policy_paths(root: Path, value: object, name: str) -> tuple[Path, ...]:
    values = _text_tuple(value, name)
    relative_paths = tuple(_relative_path(item, name) for item in values)
    if len(set(relative_paths)) != len(relative_paths):
        raise CatalogError(f"{name} repeats a path")
    return tuple(root / path for path in relative_paths)


def _catalog_locations(raw: dict[str, object]) -> tuple[CatalogLocation, ...]:
    catalogs = _table(raw.get("catalogs"), "catalogs")
    declared_zones = frozenset(catalogs)
    unknown_zones = sorted(declared_zones - ALLOWED_OWNERSHIP_ZONES)
    if unknown_zones:
        raise CatalogError(
            f"catalogs has unsupported ownership zone(s): {', '.join(unknown_zones)}"
        )
    missing_zones = sorted(ALLOWED_OWNERSHIP_ZONES - declared_zones)
    if missing_zones:
        raise CatalogError(
            f"catalogs is missing ownership zone(s): {', '.join(missing_zones)}"
        )
    locations: list[CatalogLocation] = []
    for ownership_zone in sorted(ALLOWED_OWNERSHIP_ZONES):
        name = f"catalogs.{ownership_zone}"
        for value in _text_tuple(catalogs.get(ownership_zone), name):
            path = _relative_path(value, name)
            if path == Path("policy.toml"):
                raise CatalogError("catalogs cannot include policy.toml")
            if path.suffix not in ("", ".toml"):
                raise CatalogError(
                    f"{name} path '{value}' must name a TOML file or directory"
                )
            locations.append(
                CatalogLocation(
                    ownership_zone=ownership_zone,
                    relative_path=path,
                )
            )
    paths = tuple(location.relative_path for location in locations)
    if len(set(paths)) != len(paths):
        raise CatalogError("catalogs repeats a catalog path")
    for index, path in enumerate(paths):
        for other_path in paths[index + 1 :]:
            if path in other_path.parents or other_path in path.parents:
                raise CatalogError(
                    f"catalogs paths overlap: {path.as_posix()} and {other_path.as_posix()}"
                )
    return tuple(locations)


def _load_policy(root: Path, raw: dict[str, object]) -> ProofPolicy:
    policy = _table(raw.get("policy"), "policy")
    behavior_roots = _text_tuple(policy.get("behavior_roots"), "policy.behavior_roots")
    _validate_modules(behavior_roots, "policy.behavior_roots")
    return ProofPolicy(
        source_roots=_policy_paths(
            root, policy.get("source_roots"), "policy.source_roots"
        ),
        test_roots=_policy_paths(root, policy.get("test_roots"), "policy.test_roots"),
        behavior_roots=behavior_roots,
        excluded_module_stems=frozenset(
            _text_tuple(
                policy.get("excluded_module_stems"),
                "policy.excluded_module_stems",
                allow_empty=True,
            )
        ),
        oracle_module_stems=frozenset(
            _text_tuple(policy.get("oracle_module_stems"), "policy.oracle_module_stems")
        ),
        catalog_locations=_catalog_locations(raw),
    )


def _property_identity(raw: dict[str, object], prefix: str) -> _PropertyIdentity:
    property_id = _text(raw.get("id"), f"{prefix}.id")
    if PROPERTY_ID_PATTERN.fullmatch(property_id) is None:
        raise CatalogError(
            f"Property ID '{property_id}' must use stable UPPER-KEBAB-CASE"
        )
    kind = _text(raw.get("kind"), f"{prefix}.kind")
    if kind not in ALLOWED_KINDS:
        raise CatalogError(f"Property '{property_id}' has unsupported kind '{kind}'")
    strength = _text(raw.get("strength"), f"{prefix}.strength")
    if strength not in ALLOWED_STRENGTHS:
        raise CatalogError(
            f"Property '{property_id}' must be normative before it can own production behavior"
        )
    return _PropertyIdentity(property_id=property_id, kind=kind, strength=strength)


def _property_links(
    raw: dict[str, object],
    prefix: str,
    property_id: str,
) -> _PropertyLinks:
    targets = _text_tuple(raw.get("targets"), f"{prefix}.targets")
    oracles = _text_tuple(raw.get("oracles"), f"{prefix}.oracles")
    crosshair_targets = _optional_text_tuple(
        raw.get("crosshair_targets"),
        f"{prefix}.crosshair_targets",
    )
    _validate_targets(targets, f"Property '{property_id}' targets")
    _validate_targets(oracles, f"Property '{property_id}' oracles")
    _validate_targets(crosshair_targets, f"Property '{property_id}' crosshair_targets")
    return _PropertyLinks(
        targets=targets,
        oracles=oracles,
        crosshair_targets=crosshair_targets,
    )


def _required_evidence(kind: str) -> frozenset[str]:
    if kind == "state_machine":
        return frozenset({"hypothesis-stateful", "falsifier"})
    return frozenset({"icontract", "hypothesis", "falsifier"})


def _validate_evidence_set(
    property_id: str,
    kind: str,
    evidence_values: tuple[str, ...],
) -> frozenset[str]:
    evidence = frozenset(evidence_values)
    unknown = sorted(evidence - ALLOWED_EVIDENCE)
    if unknown:
        raise CatalogError(
            f"Property '{property_id}' has unsupported evidence: {', '.join(unknown)}"
        )
    if len(evidence) != len(evidence_values):
        raise CatalogError(f"Property '{property_id}' repeats an evidence kind")
    missing = sorted(_required_evidence(kind) - evidence)
    if missing:
        raise CatalogError(
            f"Property '{property_id}' is missing required evidence: {', '.join(missing)}"
        )
    return evidence


def _validate_state_machine_evidence(
    property_id: str,
    kind: str,
    evidence: frozenset[str],
) -> None:
    if kind != "state_machine":
        return
    if "hypothesis" in evidence:
        raise CatalogError(
            f"State-machine property '{property_id}' must use hypothesis-stateful, not hypothesis"
        )
    if "crosshair" in evidence:
        message = (
            f"State-machine property '{property_id}' cannot target effectful "
            "workflow code with CrossHair"
        )
        raise CatalogError(message)


def _validate_crosshair_evidence(
    property_id: str,
    evidence: frozenset[str],
    links: _PropertyLinks,
) -> None:
    if bool(links.crosshair_targets) != ("crosshair" in evidence):
        message = (
            f"Property '{property_id}' must declare crosshair evidence and "
            "crosshair_targets together"
        )
        raise CatalogError(message)
    undeclared = sorted(set(links.crosshair_targets) - set(links.targets))
    if undeclared:
        message = (
            f"Property '{property_id}' crosshair target(s) are not property targets: "
            f"{', '.join(undeclared)}"
        )
        raise CatalogError(message)


def _load_property(value: object, index: int) -> PropertySpec:
    prefix = f"properties[{index}]"
    raw = _table(value, prefix)
    identity = _property_identity(raw, prefix)
    links = _property_links(raw, prefix, identity.property_id)
    evidence = _validate_evidence_set(
        identity.property_id,
        identity.kind,
        _text_tuple(raw.get("evidence"), f"{prefix}.evidence"),
    )
    _validate_state_machine_evidence(identity.property_id, identity.kind, evidence)
    _validate_crosshair_evidence(identity.property_id, evidence, links)
    return PropertySpec(
        property_id=identity.property_id,
        title=_text(raw.get("title"), f"{prefix}.title"),
        statement=_text(raw.get("statement"), f"{prefix}.statement"),
        scope=_text(raw.get("scope"), f"{prefix}.scope"),
        assumptions=_text_tuple(
            raw.get("assumptions"), f"{prefix}.assumptions", allow_empty=True
        ),
        kind=identity.kind,
        strength=identity.strength,
        targets=links.targets,
        oracles=links.oracles,
        evidence=evidence,
        counterexample=_text(raw.get("counterexample"), f"{prefix}.counterexample"),
        failure_modes=_text_tuple(raw.get("failure_modes"), f"{prefix}.failure_modes"),
        crosshair_targets=links.crosshair_targets,
    )


def _load_exemption(value: object, index: int) -> ProofExemption:
    prefix = f"exemptions[{index}]"
    raw = _table(value, prefix)
    target = _text(raw.get("target"), f"{prefix}.target")
    _validate_targets((target,), f"Exemption '{target}'")
    revisit_text = _text(raw.get("revisit"), f"{prefix}.revisit")
    try:
        revisit = date.fromisoformat(revisit_text)
    except ValueError as error:
        raise CatalogError(
            f"Exemption '{target}' revisit must be an ISO date (YYYY-MM-DD)"
        ) from error
    if revisit <= datetime.now(UTC).date():
        raise CatalogError(
            f"Exemption '{target}' expired on {revisit.isoformat()}; prove or remove the behavior"
        )
    return ProofExemption(
        target=target,
        reason=_text(raw.get("reason"), f"{prefix}.reason"),
        revisit=revisit,
    )


def _table_array(
    raw: dict[str, object],
    key: str,
    *,
    allow_empty: bool,
) -> list[object]:
    values = _array(raw.get(key, []), key)
    if not values and not allow_empty:
        raise CatalogError(f"{key} must be a non-empty array of tables")
    return values


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates))


def _validate_catalog_ownership(catalogs: tuple[CatalogEntry, ...]) -> None:
    property_paths: dict[str, list[Path]] = {}
    for catalog in catalogs:
        for property_spec in catalog.properties:
            property_paths.setdefault(property_spec.property_id, []).append(
                catalog.path
            )
    duplicates = {
        property_id: paths
        for property_id, paths in property_paths.items()
        if len(paths) > 1
    }
    if duplicates:
        descriptions = ", ".join(
            f"{property_id} ({', '.join(path.as_posix() for path in paths)})"
            for property_id, paths in sorted(duplicates.items())
        )
        raise DuplicatePropertyIdError(
            f"Duplicate property IDs across catalogs: {descriptions}"
        )
    exemptions = tuple(
        exemption for catalog in catalogs for exemption in catalog.exemptions
    )
    exemption_targets = tuple(item.target for item in exemptions)
    if _duplicates(exemption_targets):
        raise CatalogError("Proof catalogs repeat an exempted target")
    proven_targets = {
        target
        for catalog in catalogs
        for property_spec in catalog.properties
        for target in property_spec.targets
    }
    overlap = sorted(set(exemption_targets) & proven_targets)
    if overlap:
        raise CatalogError(
            f"Targets cannot be both proven and exempted: {', '.join(overlap)}"
        )


def _read_toml(path: Path, label: str) -> dict[str, object]:
    try:
        return _table(tomllib.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CatalogError(
            f"Cannot read {label} '{path.as_posix()}': {error}"
        ) from error


def _catalog_paths(
    proof_root: Path, policy: ProofPolicy
) -> tuple[tuple[Path, str], ...]:
    discovered: list[tuple[Path, str]] = []
    for location in policy.catalog_locations:
        path = proof_root / location.relative_path
        if location.relative_path.suffix == ".toml":
            if not path.is_file():
                raise CatalogError(f"Catalog '{path.as_posix()}' does not exist")
            discovered.append((path, location.ownership_zone))
            continue
        if not path.exists():
            continue
        if not path.is_dir():
            raise CatalogError(f"Catalog root '{path.as_posix()}' must be a directory")
        discovered.extend(
            (candidate, location.ownership_zone)
            for candidate in sorted(path.rglob("*.toml"))
            if candidate.is_file()
        )
    if not discovered:
        raise CatalogError("proof policy declares no catalog files")
    return tuple(sorted(discovered, key=lambda item: item[0].as_posix()))


def _load_catalog_entry(path: Path, ownership_zone: str) -> CatalogEntry:
    raw = _read_toml(path, "proof catalog")
    if raw.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogError(
            f"Catalog '{path.as_posix()}' schema_version must be exactly {CATALOG_SCHEMA_VERSION}"
        )
    declared_zone = _text(
        raw.get("ownership_zone"), f"Catalog '{path.as_posix()}'.ownership_zone"
    )
    if declared_zone not in ALLOWED_OWNERSHIP_ZONES:
        raise CatalogOwnershipError(
            f"Catalog '{path.as_posix()}' has unsupported ownership zone '{declared_zone}'"
        )
    if declared_zone != ownership_zone:
        raise CatalogOwnershipError(
            f"Catalog '{path.as_posix()}' declares ownership zone '{declared_zone}', "
            f"but its path belongs to '{ownership_zone}'"
        )
    return CatalogEntry(
        path=path,
        ownership_zone=declared_zone,
        properties=tuple(
            _load_property(value, index)
            for index, value in enumerate(
                _table_array(raw, "properties", allow_empty=True),
                start=1,
            )
        ),
        exemptions=tuple(
            _load_exemption(value, index)
            for index, value in enumerate(
                _table_array(raw, "exemptions", allow_empty=True),
                start=1,
            )
        ),
    )


def load_catalog(root: Path) -> ProofCatalog:
    path = root / "proof" / "policy.toml"
    raw = _read_toml(path, "proof policy")
    if raw.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise CatalogError(
            f"proof/policy.toml schema_version must be exactly {POLICY_SCHEMA_VERSION}"
        )
    if "properties" in raw or "exemptions" in raw:
        raise CatalogError(
            "proof/policy.toml must not declare properties or exemptions"
        )
    policy = _load_policy(root, raw)
    catalogs = tuple(
        _load_catalog_entry(catalog_path, ownership_zone)
        for catalog_path, ownership_zone in _catalog_paths(path.parent, policy)
    )
    _validate_catalog_ownership(catalogs)
    return ProofCatalog(
        path=path,
        policy=policy,
        catalogs=catalogs,
        properties=tuple(
            property_spec
            for catalog in catalogs
            for property_spec in catalog.properties
        ),
        exemptions=tuple(
            exemption for catalog in catalogs for exemption in catalog.exemptions
        ),
    )
