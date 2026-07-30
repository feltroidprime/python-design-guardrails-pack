"""Guarded, non-destructive capability lifecycle transitions."""

import dataclasses
from typing import Literal

from repoctl.modules.repository_generation.application.ports import (
    RepositoryConflictError,
    RepositoryPort,
)
from repoctl.modules.repository_generation.domain.intents import (
    CapabilityDeclaration,
    CapabilityStatus,
)
from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipZone,
    OwnershipZoneRoots,
    RepositoryPathCandidate,
    classify_path,
)

type ActivationEvidenceName = Literal[
    "architecture_contract",
    "stable_surface",
    "normative_property_evidence",
    "port_contract",
    "cli_process_evidence",
]
type LifecycleStatus = Literal["activated", "retired", "refused"]
type LifecycleFailure = Literal[
    "capability_not_found",
    "invalid_transition",
    "missing_evidence",
    "stale_declaration",
    "declaration_path_not_owned",
]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ActivationEvidence:
    """The explicit current evidence required before a capability can become active."""

    architecture_contract: bool
    stable_surface: bool
    normative_property_evidence: bool
    port_contract: bool
    cli_process_evidence: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class LifecycleOutcome:
    """One structured result from an activate or retire transition."""

    capability_name: str
    status: LifecycleStatus
    reason: LifecycleFailure | None = None
    missing_evidence: tuple[ActivationEvidenceName, ...] = ()


def _declaration(
    repository: RepositoryPort,
    capability_name: str,
) -> tuple[CapabilityDeclaration, str, tuple[OwnershipZoneRoots, ...]] | None:
    snapshot = repository.snapshot()
    declaration = next(
        (item for item in snapshot.declarations if item.name == capability_name),
        None,
    )
    if declaration is None:
        return None
    candidate = _declaration_path(declaration)
    return next(
        (
            (declaration, repository_file.digest, snapshot.ownership_zones)
            for repository_file in snapshot.files
            if repository_file.path.value == candidate.value
        ),
        None,
    )


def _declaration_path(declaration: CapabilityDeclaration) -> RepositoryPathCandidate:
    return RepositoryPathCandidate(value=f".repo/capabilities/{declaration.name}.toml")


def _missing_evidence(
    evidence: ActivationEvidence,
) -> tuple[ActivationEvidenceName, ...]:
    checks: tuple[tuple[bool, ActivationEvidenceName], ...] = (
        (evidence.architecture_contract, "architecture_contract"),
        (evidence.stable_surface, "stable_surface"),
        (evidence.normative_property_evidence, "normative_property_evidence"),
        (evidence.port_contract, "port_contract"),
        (evidence.cli_process_evidence, "cli_process_evidence"),
    )
    return tuple(name for present, name in checks if not present)


def _write_status(
    declaration: CapabilityDeclaration,
    expected_digest: str,
    ownership_zones: tuple[OwnershipZoneRoots, ...],
    status: CapabilityStatus,
    repository: RepositoryPort,
) -> LifecycleFailure | None:
    candidate = _declaration_path(declaration)
    if classify_path(candidate, ownership_zones) != OwnershipZone("DECLARATION"):
        return "declaration_path_not_owned"
    replacement = dataclasses.replace(declaration, status=status)
    try:
        repository.write_if_matches(
            candidate,
            replacement.canonical_document().encode("utf-8"),
            expected_digest=expected_digest,
        )
    except RepositoryConflictError:
        return "stale_declaration"
    return None


def activate(
    capability_name: str,
    evidence: ActivationEvidence,
    repository: RepositoryPort,
) -> LifecycleOutcome:
    """Activate a DRAFT or RETIRED declaration only when all current evidence passes."""
    current = _declaration(repository, capability_name)
    if current is None:
        return LifecycleOutcome(
            capability_name=capability_name,
            status="refused",
            reason="capability_not_found",
        )
    declaration, expected_digest, ownership_zones = current
    if declaration.status not in {"draft", "retired"}:
        return LifecycleOutcome(
            capability_name=capability_name,
            status="refused",
            reason="invalid_transition",
        )
    missing_evidence = _missing_evidence(evidence)
    if missing_evidence:
        return LifecycleOutcome(
            capability_name=capability_name,
            status="refused",
            reason="missing_evidence",
            missing_evidence=missing_evidence,
        )
    failure = _write_status(
        declaration,
        expected_digest,
        ownership_zones,
        "active",
        repository,
    )
    if failure is not None:
        return LifecycleOutcome(
            capability_name=capability_name,
            status="refused",
            reason=failure,
        )
    return LifecycleOutcome(capability_name=capability_name, status="activated")


def retire(capability_name: str, repository: RepositoryPort) -> LifecycleOutcome:
    """Retire a DRAFT or ACTIVE declaration without touching any product path."""
    current = _declaration(repository, capability_name)
    if current is None:
        return LifecycleOutcome(
            capability_name=capability_name,
            status="refused",
            reason="capability_not_found",
        )
    declaration, expected_digest, ownership_zones = current
    if declaration.status not in {"draft", "active"}:
        return LifecycleOutcome(
            capability_name=capability_name,
            status="refused",
            reason="invalid_transition",
        )
    failure = _write_status(
        declaration,
        expected_digest,
        ownership_zones,
        "retired",
        repository,
    )
    if failure is not None:
        return LifecycleOutcome(
            capability_name=capability_name,
            status="refused",
            reason=failure,
        )
    return LifecycleOutcome(capability_name=capability_name, status="retired")
