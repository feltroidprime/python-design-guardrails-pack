"""Structured outcomes for capability-plan application."""

from dataclasses import dataclass

from repoctl.modules.repository_generation.application.specifications import ApplyStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplyOutcome:
    """One structured, non-throwing outcome from the capability apply protocol."""

    plan_id: str
    transaction_id: str
    status: ApplyStatus
    written_targets: tuple[str, ...]
    recovery_instruction: str
