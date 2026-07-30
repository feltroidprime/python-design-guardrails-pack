"""Independent predicates for repository-generation application outcomes."""

from dataclasses import dataclass
from typing import Literal

type ApplyStatus = Literal[
    "applied",
    "already_applied",
    "invalid_plan",
    "stale_plan",
    "product_file_exists",
    "recovery_required",
    "result_mismatch",
]

RECOVERY_INSTRUCTION = "re-run capability plan against the current repository state"


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplyIdempotenceObservation:
    """Facts needed to decide whether a completed-plan replay was effect-free."""

    replay_status: ApplyStatus
    state_unchanged: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplyStalePlanObservation:
    """Facts needed to decide whether a stale application failed closed."""

    status: ApplyStatus
    recovery_instruction: str
    state_unchanged: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplyProductPreservationObservation:
    """Facts needed to decide whether an existing product file stayed unchanged."""

    status: ApplyStatus
    bytes_preserved: bool


def apply_is_idempotent(observation: ApplyIdempotenceObservation) -> bool:
    """Return whether replay reached the stable already-applied outcome without a write."""
    return observation.replay_status == "already_applied" and observation.state_unchanged


def stale_plan_is_rejected(observation: ApplyStalePlanObservation) -> bool:
    """Return whether stale state was preserved with the prescribed recovery action."""
    return (
        observation.status == "stale_plan"
        and observation.recovery_instruction == RECOVERY_INSTRUCTION
        and observation.state_unchanged
    )


def product_bytes_are_preserved(observation: ApplyProductPreservationObservation) -> bool:
    """Return whether an attempted existing-product write was refused before mutation."""
    return observation.status == "product_file_exists" and observation.bytes_preserved
