"""The ordered, stale-safe apply protocol for immutable capability plans."""

from hashlib import sha256
import json

from repoctl.modules.repository_generation.application.commands import (
    ApplyOutcome,
)
from repoctl.modules.repository_generation.application.journal import (
    JournalProtocolError,
    begin_journal,
    complete_journal,
    inspect_journal,
    record_operation,
    recover_journal,
    transaction_id_for,
)
from repoctl.modules.repository_generation.application.ports import (
    RepositoryConflictError,
    RepositoryPort,
)
from repoctl.modules.repository_generation.application.specifications import (
    RECOVERY_INSTRUCTION,
    ApplyStatus,
)
from repoctl.modules.repository_generation.domain.intents import (
    RepositoryPath,
    RepositorySnapshot,
)
from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipZone,
    RepositoryPathCandidate,
    classify_path,
)
from repoctl.modules.repository_generation.domain.plans import (
    CapabilityPlan,
    make_plan,
)
from repoctl.modules.repository_generation.domain.plans_planner import GENERATOR_VERSION


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _snapshot_digest(snapshot: RepositorySnapshot) -> str:
    """Return the planning-compatible digest of one explicit repository snapshot."""
    payload = {
        "schema_version": snapshot.schema_version,
        "package": snapshot.package,
        "declarations": [item.canonical_payload() for item in snapshot.declarations],
        "files": [
            {"target": repository_file.path.value, "digest": repository_file.digest}
            for repository_file in snapshot.files
        ],
        "ownership": [
            {
                "zone": str(zone.name),
                "roots": [root.value for root in zone.roots],
            }
            for zone in snapshot.ownership_zones
        ],
    }
    return f"sha256:{sha256(_canonical_json_bytes(payload)).hexdigest()}"


def _bytes_digest(content: bytes | None) -> str:
    return "absent" if content is None else f"sha256:{sha256(content).hexdigest()}"


def _port_path(path: RepositoryPath) -> RepositoryPathCandidate:
    """Re-enter the port's explicit untrusted-path boundary for one plan target."""
    return RepositoryPathCandidate(value=path.value)


def _valid_plan(plan: CapabilityPlan) -> bool:
    """Validate schema, generator identity, content-derived ID, and operation content."""
    expected = make_plan(
        generator_version=plan.generator_version,
        base_state_digest=plan.base_state_digest,
        intent=plan.intent,
        operations=plan.operations,
        result_state_digest=plan.result_state_digest,
    )
    return (
        plan.schema_version == 1
        and plan.generator_version == GENERATOR_VERSION
        and expected == plan
        and all(
            _bytes_digest(operation.content.encode("utf-8")) == operation.content_digest
            for operation in plan.operations
        )
    )


def _outcome(
    plan: CapabilityPlan,
    *,
    status: ApplyStatus,
    written_targets: tuple[str, ...] = (),
    recovery_instruction: str = "",
) -> ApplyOutcome:
    return ApplyOutcome(
        plan_id=plan.plan_id,
        transaction_id=transaction_id_for(plan),
        status=status,
        written_targets=written_targets,
        recovery_instruction=recovery_instruction,
    )


def _preflight_operations(
    plan: CapabilityPlan,
    snapshot: RepositorySnapshot,
    repository: RepositoryPort,
) -> ApplyStatus | None:
    """Reject existing product bytes and stale compare-and-swap values before journaling."""
    for operation in plan.operations:
        repository_path = _port_path(operation.path)
        current = repository.read_bytes(repository_path)
        if current is not None and classify_path(
            repository_path, snapshot.ownership_zones
        ) == OwnershipZone("PRODUCT"):
            return "product_file_exists"
        if _bytes_digest(current) != operation.precondition:
            return "stale_plan"
    return None


def _recovery_outcome(plan: CapabilityPlan) -> ApplyOutcome:
    return _outcome(
        plan,
        status="recovery_required",
        recovery_instruction=RECOVERY_INSTRUCTION,
    )


def _recover_after_partial_apply(plan: CapabilityPlan, repository: RepositoryPort) -> ApplyOutcome:
    try:
        _ = recover_journal(plan, repository)
    except JournalProtocolError:
        pass
    return _recovery_outcome(plan)


def _journal_state_outcome(
    plan: CapabilityPlan,
    *,
    journal_state: str,
    state_digest: str,
) -> ApplyOutcome | None:
    if journal_state == "complete":
        if state_digest == plan.result_state_digest:
            return _outcome(plan, status="already_applied")
        return _outcome(
            plan,
            status="stale_plan",
            recovery_instruction=RECOVERY_INSTRUCTION,
        )
    if journal_state in {"incomplete", "recovered"}:
        return _recovery_outcome(plan)
    return None


def _preflight_outcome(plan: CapabilityPlan, repository: RepositoryPort) -> ApplyOutcome | None:
    if not _valid_plan(plan):
        return _outcome(plan, status="invalid_plan")
    try:
        journal = inspect_journal(plan, repository)
    except JournalProtocolError:
        return _recovery_outcome(plan)
    snapshot = repository.snapshot()
    state_digest = _snapshot_digest(snapshot)
    journal_outcome = _journal_state_outcome(
        plan,
        journal_state=journal.state,
        state_digest=state_digest,
    )
    if journal_outcome is not None:
        return journal_outcome
    if state_digest != plan.base_state_digest:
        return _outcome(
            plan,
            status="stale_plan",
            recovery_instruction=RECOVERY_INSTRUCTION,
        )
    preflight_status = _preflight_operations(plan, snapshot, repository)
    if preflight_status is not None:
        return _outcome(
            plan,
            status=preflight_status,
            recovery_instruction=(RECOVERY_INSTRUCTION if preflight_status == "stale_plan" else ""),
        )
    return None


def _apply_new_transaction(plan: CapabilityPlan, repository: RepositoryPort) -> ApplyOutcome:
    """Journal and execute a fully preflighted plan in its canonical operation order."""
    _ = begin_journal(plan, repository)
    written_targets: list[str] = []
    try:
        for operation in plan.operations:
            _ = record_operation(plan, operation, repository)
            repository.write_if_matches(
                _port_path(operation.path),
                operation.content.encode("utf-8"),
                expected_digest=operation.precondition,
            )
            written_targets.append(operation.path.value)
    except JournalProtocolError, RepositoryConflictError:
        return _recover_after_partial_apply(plan, repository)

    if _snapshot_digest(repository.snapshot()) != plan.result_state_digest:
        return _recover_after_partial_apply(plan, repository)
    try:
        _ = complete_journal(plan, repository)
    except JournalProtocolError:
        return _recover_after_partial_apply(plan, repository)
    return _outcome(plan, status="applied", written_targets=tuple(written_targets))


def apply(plan: CapabilityPlan, repository: RepositoryPort) -> ApplyOutcome:
    """Apply one immutable plan once, failing closed before any stale or unsafe write."""
    preflight_outcome = _preflight_outcome(plan, repository)
    if preflight_outcome is not None:
        return preflight_outcome
    return _apply_new_transaction(plan, repository)
