"""Stateful evidence for stale-safe, journaled capability-plan application."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import final

from hypothesis.stateful import RuleBasedStateMachine, rule
import pytest

from repoctl.modules.repository_generation.api import (
    RECOVERY_INSTRUCTION,
    ApplyIdempotenceObservation,
    ApplyProductPreservationObservation,
    ApplyStalePlanObservation,
    CapabilityIntent,
    CapabilityPlan,
    LocalRepository,
    MemoryRepository,
    Operation,
    RepositoryPath,
    RepositoryPathCandidate,
    RepositorySnapshot,
    TransactionInspection,
    TransactionMissingError,
    apply,
    apply_is_idempotent,
    content_digest,
    make_plan,
    plan,
    product_bytes_are_preserved,
    stale_plan_is_rejected,
    transaction_id_for,
)
from verification.harness.assertions import assert_falsifies, assert_property
from verification.harness.stateful import run_state_machine_as_test


def _intent() -> CapabilityIntent:
    return CapabilityIntent(
        schema_version=1,
        name="planned_capability",
        inbound=("cli", "python"),
        outbound=("clock",),
    )


def _port_path(path: RepositoryPath) -> RepositoryPathCandidate:
    return RepositoryPathCandidate(value=path.value)


def _planned_memory_repository() -> tuple[MemoryRepository, CapabilityPlan]:
    repository = MemoryRepository()
    return repository, plan(repository.snapshot(), _intent())


def _transaction_facts(
    repository: MemoryRepository,
    capability_plan: CapabilityPlan,
) -> tuple[str, tuple[str, ...]]:
    transaction_id = transaction_id_for(capability_plan)
    try:
        inspection = repository.inspect_transaction(transaction_id)
    except TransactionMissingError:
        return "absent", ()
    return inspection.state, tuple(entry.decode("utf-8") for entry in inspection.entries)


def _stored_state_digest(repository: MemoryRepository, capability_plan: CapabilityPlan) -> str:
    snapshot = repository.snapshot()
    transaction_state, transaction_entries = _transaction_facts(repository, capability_plan)
    payload = repr(
        (
            tuple((file.path.value, file.digest) for file in snapshot.files),
            transaction_state,
            transaction_entries,
        )
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _existing_product_scenario() -> tuple[
    MemoryRepository,
    CapabilityPlan,
    RepositoryPath,
    bytes,
]:
    target = RepositoryPath(value="src/acme/modules/existing_capability/api.py")
    original = b'"""Existing product bytes."""\n'
    repository = MemoryRepository(initial_contents={_port_path(target): original})
    seed_plan = plan(repository.snapshot(), _intent())
    replacement = '"""Replacement bytes."""\n'
    capability_plan = make_plan(
        generator_version=seed_plan.generator_version,
        base_state_digest=seed_plan.base_state_digest,
        intent=seed_plan.intent,
        operations=(
            Operation(
                kind="create_product_seed",
                path=target,
                precondition=content_digest(original.decode("utf-8")),
                content=replacement,
                content_digest=content_digest(replacement),
            ),
        ),
        result_state_digest=seed_plan.result_state_digest,
    )
    return repository, capability_plan, target, original


@final
class ApplyRetryMachine(RuleBasedStateMachine):
    """Search arbitrary replay histories after a plan has completed once."""

    _repository: MemoryRepository
    _plan: CapabilityPlan

    def __init__(self) -> None:
        super().__init__()
        self._repository, self._plan = _planned_memory_repository()
        outcome = apply(self._plan, self._repository)
        assert outcome.status == "applied"

    @rule()
    def replay_completed_plan(self) -> None:
        before = _stored_state_digest(self._repository, self._plan)
        outcome = apply(self._plan, self._repository)
        after = _stored_state_digest(self._repository, self._plan)

        assert_property(
            condition=apply_is_idempotent(
                ApplyIdempotenceObservation(
                    replay_status=outcome.status,
                    state_unchanged=after == before,
                )
            ),
            property_id="REPOCTL::APPLY-IDEMPOTENT",
        )


@final
class StalePlanMachine(RuleBasedStateMachine):
    """Search the history in which an inspected plan becomes stale before apply."""

    _repository: MemoryRepository
    _plan: CapabilityPlan

    def __init__(self) -> None:
        super().__init__()
        self._repository, self._plan = _planned_memory_repository()
        target = RepositoryPath(value="docs/product/intervening-change.md")
        self._repository.write_if_matches(
            _port_path(target), b"changed\n", expected_digest="absent"
        )

    @rule()
    def reject_stale_plan_without_writing(self) -> None:
        before = _stored_state_digest(self._repository, self._plan)
        outcome = apply(self._plan, self._repository)
        after = _stored_state_digest(self._repository, self._plan)

        assert_property(
            condition=stale_plan_is_rejected(
                ApplyStalePlanObservation(
                    status=outcome.status,
                    recovery_instruction=outcome.recovery_instruction,
                    state_unchanged=after == before,
                )
            ),
            property_id="REPOCTL::STALE-PLAN-REJECTED",
        )


@final
class ExistingProductMachine(RuleBasedStateMachine):
    """Search repeated attempts to overwrite an already-present product seed."""

    _target: RepositoryPath
    _original: bytes
    _repository: MemoryRepository
    _plan: CapabilityPlan

    def __init__(self) -> None:
        super().__init__()
        (
            self._repository,
            self._plan,
            self._target,
            self._original,
        ) = _existing_product_scenario()

    @rule()
    def refuse_existing_product_seed(self) -> None:
        before = self._repository.read_bytes(_port_path(self._target))
        outcome = apply(self._plan, self._repository)
        after = self._repository.read_bytes(_port_path(self._target))

        assert_property(
            condition=product_bytes_are_preserved(
                ApplyProductPreservationObservation(
                    status=outcome.status,
                    bytes_preserved=after == before == self._original,
                )
            ),
            property_id="REPOCTL::PRODUCT-BYTES-PRESERVED",
        )


@pytest.mark.proof
@pytest.mark.stateful
@pytest.mark.proves("REPOCTL::APPLY-IDEMPOTENT")
def test_completed_plan_replays_are_idempotent() -> None:
    run_state_machine_as_test(ApplyRetryMachine)


@pytest.mark.proof
@pytest.mark.stateful
@pytest.mark.proves("REPOCTL::STALE-PLAN-REJECTED")
def test_stale_plans_are_rejected_without_writes() -> None:
    run_state_machine_as_test(StalePlanMachine)


@pytest.mark.proof
@pytest.mark.stateful
@pytest.mark.proves("REPOCTL::PRODUCT-BYTES-PRESERVED")
def test_existing_product_bytes_are_preserved() -> None:
    run_state_machine_as_test(ExistingProductMachine)


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::APPLY-IDEMPOTENT")
def test_changed_state_on_replay_is_a_real_counterexample() -> None:
    assert_falsifies(
        condition=apply_is_idempotent(
            ApplyIdempotenceObservation(
                replay_status="already_applied",
                state_unchanged=False,
            )
        ),
        property_id="REPOCTL::APPLY-IDEMPOTENT",
    )


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::STALE-PLAN-REJECTED")
def test_stale_write_without_recovery_is_a_real_counterexample() -> None:
    assert_falsifies(
        condition=stale_plan_is_rejected(
            ApplyStalePlanObservation(
                status="applied",
                recovery_instruction="",
                state_unchanged=False,
            )
        ),
        property_id="REPOCTL::STALE-PLAN-REJECTED",
    )


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::PRODUCT-BYTES-PRESERVED")
def test_replaced_product_bytes_are_a_real_counterexample() -> None:
    assert_falsifies(
        condition=product_bytes_are_preserved(
            ApplyProductPreservationObservation(
                status="applied",
                bytes_preserved=False,
            )
        ),
        property_id="REPOCTL::PRODUCT-BYTES-PRESERVED",
    )


def test_stale_plan_contains_recovery_guidance_and_preserves_full_state() -> None:
    repository, capability_plan = _planned_memory_repository()
    repository.write_if_matches(
        _port_path(RepositoryPath(value="docs/product/intervening-change.md")),
        b"changed\n",
        expected_digest="absent",
    )
    before = _stored_state_digest(repository, capability_plan)

    outcome = apply(capability_plan, repository)

    after = _stored_state_digest(repository, capability_plan)
    assert outcome.status == "stale_plan"
    assert outcome.recovery_instruction == RECOVERY_INSTRUCTION
    assert after == before


def test_existing_product_seed_is_refused_even_when_its_precondition_matches() -> None:
    repository, capability_plan, target, original = _existing_product_scenario()
    before = repository.read_bytes(_port_path(target))

    outcome = apply(capability_plan, repository)

    assert outcome.status == "product_file_exists"
    assert repository.read_bytes(_port_path(target)) == before == original


@dataclass(slots=True)
class RecordingRepository:
    """A local-port proxy that records only application file writes."""

    repository: LocalRepository
    written_targets: list[str]

    def snapshot(self) -> RepositorySnapshot:
        return self.repository.snapshot()

    def read_bytes(self, repository_path: RepositoryPathCandidate) -> bytes | None:
        return self.repository.read_bytes(repository_path)

    def ensure_directory(self, repository_path: RepositoryPathCandidate) -> None:
        self.repository.ensure_directory(repository_path)

    def write_if_matches(
        self,
        repository_path: RepositoryPathCandidate,
        content: bytes,
        *,
        expected_digest: str,
    ) -> None:
        self.repository.write_if_matches(
            repository_path,
            content,
            expected_digest=expected_digest,
        )
        self.written_targets.append(repository_path.value)

    def begin_transaction(self, transaction_id: str) -> None:
        self.repository.begin_transaction(transaction_id)

    def append_transaction_entry(self, transaction_id: str, entry: bytes) -> None:
        self.repository.append_transaction_entry(transaction_id, entry)

    def inspect_transaction(self, transaction_id: str) -> TransactionInspection:
        return self.repository.inspect_transaction(transaction_id)

    def complete_transaction(self, transaction_id: str) -> None:
        self.repository.complete_transaction(transaction_id)

    def recover_transaction(self, transaction_id: str) -> TransactionInspection:
        return self.repository.recover_transaction(transaction_id)


def test_apply_writes_exactly_the_planned_targets_on_disk(tmp_path: Path) -> None:
    local = LocalRepository(root=tmp_path)
    repository = RecordingRepository(repository=local, written_targets=[])
    capability_plan = plan(repository.snapshot(), _intent())

    outcome = apply(capability_plan, repository)

    expected_targets = {operation.path.value for operation in capability_plan.operations}
    actual_targets = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
        and not path.relative_to(tmp_path).as_posix().startswith(".repo/transactions/")
    }
    assert outcome.status == "applied"
    assert set(repository.written_targets) == expected_targets
    assert actual_targets == expected_targets
