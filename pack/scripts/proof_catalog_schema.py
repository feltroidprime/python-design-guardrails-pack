"""TOML schema parsing for a policy and its independent property catalogs."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
import re
import tomllib
from typing import cast

from scripts.proof_catalog_model import (
    ALLOWED_OWNERSHIP_ZONES,
    CatalogError,
    CatalogLocation,
    ProofExemption,
    ProofPolicy,
    PropertySpec,
)

PROPERTY_ID_BODY = (
    r"(?:[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*::)?"
    r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+"
)
PROPERTY_ID_PATTERN = re.compile(rf"^{PROPERTY_ID_BODY}$")
TARGET_PATTERN = re.compile(r"^[a-z_][a-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")
MODULE_PATTERN = re.compile(r"^[a-z_][a-z0-9_.]*$")
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
ALLOWED_STRENGTHS = frozenset({"normative"})


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


def table(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CatalogError(f"{name} must be a TOML table")
    return cast("dict[str, object]", value)


def _array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise CatalogError(f"{name} must be an array")
    return cast("list[object]", value)


def text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{name} must be a non-blank string")
    return value.strip()


def text_tuple(value: object, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    values = _array(value, name)
    if not values and not allow_empty:
        raise CatalogError(f"{name} must be a non-empty array of non-blank strings")
    return tuple(text(item, f"{name} item") for item in values)


def _optional_text_tuple(value: object | None, name: str) -> tuple[str, ...]:
    return () if value is None else text_tuple(value, name, allow_empty=True)


def _validate_targets(values: tuple[str, ...], name: str) -> None:
    invalid = tuple(value for value in values if TARGET_PATTERN.fullmatch(value) is None)
    if invalid:
        raise CatalogError(f"{name} contains invalid target(s): {', '.join(invalid)}")
    if len(set(values)) != len(values):
        raise CatalogError(f"{name} repeats a target")


def _validate_modules(values: tuple[str, ...], name: str) -> None:
    invalid = tuple(value for value in values if MODULE_PATTERN.fullmatch(value) is None)
    if invalid:
        raise CatalogError(f"{name} contains invalid module(s): {', '.join(invalid)}")


def _relative_path(path: Path, name: str) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise CatalogError(f"{name} must be a repository-relative path")
    return path


def _policy_paths(root: Path, value: object, name: str) -> tuple[Path, ...]:
    relative_paths = tuple(_relative_path(Path(item), name) for item in text_tuple(value, name))
    if len(set(relative_paths)) != len(relative_paths):
        raise CatalogError(f"{name} repeats a path")
    return tuple(root / path for path in relative_paths)


def _validate_catalog_zones(catalogs: dict[str, object]) -> None:
    declared_zones = frozenset(catalogs)
    unknown_zones = sorted(declared_zones - ALLOWED_OWNERSHIP_ZONES)
    if unknown_zones:
        raise CatalogError(
            f"catalogs has unsupported ownership zone(s): {', '.join(unknown_zones)}"
        )
    missing_zones = sorted(ALLOWED_OWNERSHIP_ZONES - declared_zones)
    if missing_zones:
        raise CatalogError(f"catalogs is missing ownership zone(s): {', '.join(missing_zones)}")


def _catalog_location(relative_path: Path, name: str, ownership_zone: str) -> CatalogLocation:
    relative_path = _relative_path(relative_path, name)
    if relative_path == Path("policy.toml"):
        raise CatalogError("catalogs cannot include policy.toml")
    if relative_path.suffix not in ("", ".toml"):
        raise CatalogError(
            f"{name} location '{relative_path.as_posix()}' must name a TOML file or directory"
        )
    return CatalogLocation(
        ownership_zone=ownership_zone,
        relative_path=relative_path,
    )


def _catalog_locations(raw: dict[str, object]) -> tuple[CatalogLocation, ...]:
    catalogs = table(raw.get("catalogs"), "catalogs")
    _validate_catalog_zones(catalogs)
    locations: list[CatalogLocation] = []
    for ownership_zone in sorted(ALLOWED_OWNERSHIP_ZONES):
        name = f"catalogs.{ownership_zone}"
        locations.extend(
            _catalog_location(Path(value), name, ownership_zone)
            for value in text_tuple(catalogs.get(ownership_zone), name)
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


def load_policy(root: Path, package: str, raw: dict[str, object]) -> ProofPolicy:
    """Load one proof policy. Behavior roots are relative to the package."""
    policy = table(raw.get("policy"), "policy")
    declared_roots = text_tuple(policy.get("behavior_roots"), "policy.behavior_roots")
    _validate_modules(declared_roots, "policy.behavior_roots")
    behavior_roots = tuple(f"{package}.{module}" for module in declared_roots)
    return ProofPolicy(
        source_roots=_policy_paths(root, policy.get("source_roots"), "policy.source_roots"),
        test_roots=_policy_paths(root, policy.get("test_roots"), "policy.test_roots"),
        behavior_roots=behavior_roots,
        excluded_module_stems=frozenset(
            text_tuple(
                policy.get("excluded_module_stems"),
                "policy.excluded_module_stems",
                allow_empty=True,
            )
        ),
        oracle_module_stems=frozenset(
            text_tuple(policy.get("oracle_module_stems"), "policy.oracle_module_stems")
        ),
        catalog_locations=_catalog_locations(raw),
    )


def _property_identity(raw: dict[str, object], prefix: str) -> _PropertyIdentity:
    property_id = text(raw.get("id"), f"{prefix}.id")
    if PROPERTY_ID_PATTERN.fullmatch(property_id) is None:
        raise CatalogError(
            " ".join(
                (
                    f"Property ID '{property_id}' must use stable UPPER-KEBAB-CASE,",
                    "optionally namespaced as UPPER-KEBAB::UPPER-KEBAB-CASE",
                )
            )
        )
    kind = text(raw.get("kind"), f"{prefix}.kind")
    if kind not in ALLOWED_KINDS:
        raise CatalogError(f"Property '{property_id}' has unsupported kind '{kind}'")
    strength = text(raw.get("strength"), f"{prefix}.strength")
    if strength not in ALLOWED_STRENGTHS:
        raise CatalogError(
            f"Property '{property_id}' must be normative before it can own production behavior"
        )
    return _PropertyIdentity(property_id=property_id, kind=kind, strength=strength)


def _property_links(raw: dict[str, object], prefix: str, property_id: str) -> _PropertyLinks:
    targets = text_tuple(raw.get("targets"), f"{prefix}.targets")
    oracles = text_tuple(raw.get("oracles"), f"{prefix}.oracles")
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
    return (
        frozenset({"hypothesis-stateful", "falsifier"})
        if kind == "state_machine"
        else frozenset({"icontract", "hypothesis", "falsifier"})
    )


def _validate_evidence(
    property_id: str, kind: str, evidence_values: tuple[str, ...]
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


def _validate_state_machine(property_id: str, kind: str, evidence: frozenset[str]) -> None:
    if kind != "state_machine":
        return
    if "hypothesis" in evidence:
        raise CatalogError(
            f"State-machine property '{property_id}' must use hypothesis-stateful, not hypothesis"
        )
    if "crosshair" in evidence:
        raise CatalogError(
            " ".join(
                (
                    f"State-machine property '{property_id}' cannot target effectful",
                    "workflow code with CrossHair",
                )
            )
        )


def _validate_crosshair(property_id: str, evidence: frozenset[str], links: _PropertyLinks) -> None:
    if bool(links.crosshair_targets) != ("crosshair" in evidence):
        raise CatalogError(
            " ".join(
                (
                    f"Property '{property_id}' must declare crosshair evidence and",
                    "crosshair_targets together",
                )
            )
        )
    undeclared = sorted(set(links.crosshair_targets) - set(links.targets))
    if undeclared:
        raise CatalogError(
            " ".join(
                (
                    f"Property '{property_id}' crosshair target(s) are not property targets:",
                    ", ".join(undeclared),
                )
            )
        )


def load_property(value: object, index: int) -> PropertySpec:
    prefix = f"properties[{index}]"
    raw = table(value, prefix)
    identity = _property_identity(raw, prefix)
    links = _property_links(raw, prefix, identity.property_id)
    evidence = _validate_evidence(
        identity.property_id,
        identity.kind,
        text_tuple(raw.get("evidence"), f"{prefix}.evidence"),
    )
    _validate_state_machine(identity.property_id, identity.kind, evidence)
    _validate_crosshair(identity.property_id, evidence, links)
    return PropertySpec(
        property_id=identity.property_id,
        title=text(raw.get("title"), f"{prefix}.title"),
        statement=text(raw.get("statement"), f"{prefix}.statement"),
        scope=text(raw.get("scope"), f"{prefix}.scope"),
        assumptions=text_tuple(raw.get("assumptions"), f"{prefix}.assumptions", allow_empty=True),
        kind=identity.kind,
        strength=identity.strength,
        targets=links.targets,
        oracles=links.oracles,
        evidence=evidence,
        counterexample=text(raw.get("counterexample"), f"{prefix}.counterexample"),
        failure_modes=text_tuple(raw.get("failure_modes"), f"{prefix}.failure_modes"),
        crosshair_targets=links.crosshair_targets,
    )


def load_exemption(value: object, index: int) -> ProofExemption:
    prefix = f"exemptions[{index}]"
    raw = table(value, prefix)
    target = text(raw.get("target"), f"{prefix}.target")
    _validate_targets((target,), f"Exemption '{target}'")
    revisit_text = text(raw.get("revisit"), f"{prefix}.revisit")
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
        reason=text(raw.get("reason"), f"{prefix}.reason"),
        revisit=revisit,
    )


def table_array(raw: dict[str, object], key: str, *, allow_empty: bool) -> list[object]:
    values = _array(raw.get(key, []), key)
    if not values and not allow_empty:
        raise CatalogError(f"{key} must be a non-empty array of tables")
    return values


def duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return tuple(sorted(repeated))


def read_toml(path: Path, label: str) -> dict[str, object]:
    try:
        return table(tomllib.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CatalogError(f"Cannot read {label} '{path.as_posix()}': {error}") from error
