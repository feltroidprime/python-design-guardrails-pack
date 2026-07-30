"""Application-owned records for durable, recoverable capability-plan transactions."""

from dataclasses import dataclass
import json
from typing import Literal, cast

from repoctl.modules.repository_generation.application.ports import (
    RepositoryPort,
    TransactionInspection,
    TransactionMissingError,
)
from repoctl.modules.repository_generation.domain.plans import CapabilityPlan, Operation

type JournalState = Literal["absent", "incomplete", "complete", "recovered"]

_JOURNAL_SCHEMA_VERSION = 1


class JournalProtocolError(ValueError):
    """Raised when an application journal cannot safely describe its plan."""


@dataclass(frozen=True, slots=True, kw_only=True)
class JournalProgress:
    """Parsed durable progress for one plan-derived transaction identifier."""

    transaction_id: str
    plan_id: str
    base_state_digest: str
    state: JournalState
    recorded_targets: tuple[str, ...]
    stopped_at: str
    completion_recorded: bool


def transaction_id_for(plan: CapabilityPlan) -> str:
    """Return the stable journal identity for one exact, content-addressed plan."""
    return f"apply:{plan.plan_id}"


def _canonical_record(values: dict[str, object]) -> bytes:
    return json.dumps(
        values,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _plan_record(plan: CapabilityPlan, transaction_id: str) -> dict[str, object]:
    return {
        "schema_version": _JOURNAL_SCHEMA_VERSION,
        "event": "plan",
        "transaction_id": transaction_id,
        "plan_id": plan.plan_id,
        "base_state_digest": plan.base_state_digest,
    }


def _operation_record(operation: Operation, sequence: int) -> dict[str, object]:
    return {
        "schema_version": _JOURNAL_SCHEMA_VERSION,
        "event": "operation",
        "sequence": sequence,
        "kind": operation.kind,
        "path": operation.path.value,
        "precondition": operation.precondition,
        "content_digest": operation.content_digest,
    }


def _completion_record(plan: CapabilityPlan) -> dict[str, object]:
    return {
        "schema_version": _JOURNAL_SCHEMA_VERSION,
        "event": "complete",
        "result_state_digest": plan.result_state_digest,
    }


def _document(entry: bytes) -> dict[str, object]:
    try:
        value = cast("object", json.loads(entry))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise JournalProtocolError("Journal entry is not UTF-8 JSON.") from error
    if not isinstance(value, dict):
        raise JournalProtocolError("Journal entry must be a JSON object.")
    return cast("dict[str, object]", value)


def _absent_progress(plan: CapabilityPlan) -> JournalProgress:
    return JournalProgress(
        transaction_id=transaction_id_for(plan),
        plan_id=plan.plan_id,
        base_state_digest=plan.base_state_digest,
        state="absent",
        recorded_targets=(),
        stopped_at="",
        completion_recorded=False,
    )


def _progress(plan: CapabilityPlan, inspection: TransactionInspection) -> JournalProgress:
    records = tuple(_document(entry) for entry in inspection.entries)
    if not records:
        return JournalProgress(
            transaction_id=inspection.transaction_id,
            plan_id=plan.plan_id,
            base_state_digest=plan.base_state_digest,
            state=inspection.state,
            recorded_targets=(),
            stopped_at="",
            completion_recorded=False,
        )
    expected_header = _plan_record(plan, inspection.transaction_id)
    if records[0] != expected_header:
        raise JournalProtocolError("Journal header does not describe the requested plan.")
    recorded_targets, completion_recorded = _recorded_operations(plan, records[1:])
    if inspection.state == "complete" and not completion_recorded:
        raise JournalProtocolError("A completed transaction requires a terminal completion record.")
    stopped_at = (
        "" if inspection.state == "complete" else recorded_targets[-1] if recorded_targets else ""
    )
    return JournalProgress(
        transaction_id=inspection.transaction_id,
        plan_id=plan.plan_id,
        base_state_digest=plan.base_state_digest,
        state=inspection.state,
        recorded_targets=recorded_targets,
        stopped_at=stopped_at,
        completion_recorded=completion_recorded,
    )


def _recorded_operations(
    plan: CapabilityPlan,
    records: tuple[dict[str, object], ...],
) -> tuple[tuple[str, ...], bool]:
    paths: list[str] = []
    completion_recorded = False
    for record in records:
        event = record.get("event")
        if event == "operation":
            if completion_recorded or len(paths) >= len(plan.operations):
                raise JournalProtocolError("Journal operation record is out of order.")
            expected = _operation_record(plan.operations[len(paths)], len(paths))
            if record != expected:
                raise JournalProtocolError("Journal operation record does not match the plan.")
            paths.append(plan.operations[len(paths)].path.value)
            continue
        if event == "complete":
            if completion_recorded or len(paths) != len(plan.operations):
                raise JournalProtocolError("Journal completion record is out of order.")
            if record != _completion_record(plan):
                raise JournalProtocolError("Journal completion record does not match the plan.")
            completion_recorded = True
            continue
        raise JournalProtocolError("Journal entry has an unknown event.")
    return tuple(paths), completion_recorded


def inspect_journal(plan: CapabilityPlan, repository: RepositoryPort) -> JournalProgress:
    """Classify durable journal state without mutating the repository."""
    transaction_id = transaction_id_for(plan)
    try:
        inspection = repository.inspect_transaction(transaction_id)
    except TransactionMissingError:
        return _absent_progress(plan)
    return _progress(plan, inspection)


def begin_journal(plan: CapabilityPlan, repository: RepositoryPort) -> JournalProgress:
    """Create and identify a plan journal exactly once, preserving prior durable state."""
    progress = inspect_journal(plan, repository)
    if progress.state != "absent":
        return progress
    repository.begin_transaction(progress.transaction_id)
    repository.append_transaction_entry(
        progress.transaction_id,
        _canonical_record(_plan_record(plan, progress.transaction_id)),
    )
    return inspect_journal(plan, repository)


def record_operation(
    plan: CapabilityPlan,
    operation: Operation,
    repository: RepositoryPort,
) -> JournalProgress:
    """Append one planned operation only at its deterministic journal position."""
    progress = inspect_journal(plan, repository)
    if progress.state == "complete":
        return progress
    if progress.state != "incomplete" or progress.completion_recorded:
        raise JournalProtocolError(
            "Only an unfinished, nonterminal journal can record an operation."
        )
    sequence = len(progress.recorded_targets)
    if sequence >= len(plan.operations) or plan.operations[sequence] != operation:
        raise JournalProtocolError("Journal operations must follow the plan's canonical order.")
    repository.append_transaction_entry(
        progress.transaction_id,
        _canonical_record(_operation_record(operation, sequence)),
    )
    return inspect_journal(plan, repository)


def complete_journal(plan: CapabilityPlan, repository: RepositoryPort) -> JournalProgress:
    """Record the terminal marker and durably complete a fully recorded plan journal."""
    progress = inspect_journal(plan, repository)
    if progress.state == "complete":
        return progress
    if progress.state != "incomplete" or len(progress.recorded_targets) != len(plan.operations):
        raise JournalProtocolError("Only a fully recorded incomplete journal can be completed.")
    if not progress.completion_recorded:
        repository.append_transaction_entry(
            progress.transaction_id,
            _canonical_record(_completion_record(plan)),
        )
    repository.complete_transaction(progress.transaction_id)
    return inspect_journal(plan, repository)


def recover_journal(plan: CapabilityPlan, repository: RepositoryPort) -> JournalProgress:
    """Mark an incomplete journal recovered and return its non-complete classification."""
    progress = inspect_journal(plan, repository)
    if progress.state == "incomplete":
        _ = repository.recover_transaction(progress.transaction_id)
    return inspect_journal(plan, repository)
