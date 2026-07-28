"""Schema and loader for the repository's closed property catalog."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
import re
import tomllib
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

PROPERTY_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
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
# A discovered candidate may be useful during design, but it cannot close the
# production proof surface. Agents must promote accepted laws to normative.
ALLOWED_STRENGTHS = frozenset({"normative"})


class CatalogError(ValueError):
    """Raised when ``proof.toml`` is not a closed, valid specification."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ProofPolicy:
    source_root: Path
    test_root: Path
    behavior_roots: tuple[str, ...]
    excluded_module_stems: frozenset[str]
    oracle_module_stems: frozenset[str]


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
class ProofCatalog:
    path: Path
    policy: ProofPolicy
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


def _text_tuple(value: object, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    values = _array(value, name)
    if not values and not allow_empty:
        raise CatalogError(f"{name} must be a non-empty array of non-blank strings")
    return tuple(_text(item, f"{name} item") for item in values)


def _optional_text_tuple(value: object | None, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    return _text_tuple(value, name, allow_empty=True)


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


def _load_policy(root: Path, raw: object) -> ProofPolicy:
    policy = _table(raw, "policy")
    behavior_roots = _text_tuple(policy.get("behavior_roots"), "policy.behavior_roots")
    _validate_modules(behavior_roots, "policy.behavior_roots")
    return ProofPolicy(
        source_root=root / _text(policy.get("source_root"), "policy.source_root"),
        test_root=root / _text(policy.get("test_root"), "policy.test_root"),
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
    )


def _property_identity(raw: dict[str, object], prefix: str) -> _PropertyIdentity:
    property_id = _text(raw.get("id"), f"{prefix}.id")
    if PROPERTY_ID_PATTERN.fullmatch(property_id) is None:
        raise CatalogError(f"Property ID '{property_id}' must use stable UPPER-KEBAB-CASE")
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
        assumptions=_text_tuple(raw.get("assumptions"), f"{prefix}.assumptions", allow_empty=True),
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


def _validate_catalog_ownership(
    properties: tuple[PropertySpec, ...],
    exemptions: tuple[ProofExemption, ...],
) -> None:
    duplicate_ids = _duplicates(tuple(item.property_id for item in properties))
    if duplicate_ids:
        raise CatalogError(f"Duplicate property IDs: {', '.join(duplicate_ids)}")
    exemption_targets = tuple(item.target for item in exemptions)
    if _duplicates(exemption_targets):
        raise CatalogError("proof.toml repeats an exempted target")
    proven_targets = {target for property_spec in properties for target in property_spec.targets}
    overlap = sorted(set(exemption_targets) & proven_targets)
    if overlap:
        raise CatalogError(f"Targets cannot be both proven and exempted: {', '.join(overlap)}")


def _read_catalog(path: Path) -> dict[str, object]:
    try:
        return _table(tomllib.loads(path.read_text(encoding="utf-8")), "proof.toml")
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CatalogError(f"Cannot read proof.toml: {error}") from error


def load_catalog(root: Path) -> ProofCatalog:
    path = root / "proof.toml"
    raw = _read_catalog(path)
    if raw.get("schema_version") != 1:
        raise CatalogError("proof.toml schema_version must be exactly 1")
    properties = tuple(
        _load_property(value, index)
        for index, value in enumerate(_table_array(raw, "properties", allow_empty=False), start=1)
    )
    exemptions = tuple(
        _load_exemption(value, index)
        for index, value in enumerate(_table_array(raw, "exemptions", allow_empty=True), start=1)
    )
    _validate_catalog_ownership(properties, exemptions)
    return ProofCatalog(
        path=path,
        policy=_load_policy(root, raw.get("policy")),
        properties=properties,
        exemptions=exemptions,
    )
