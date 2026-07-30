"""Application-level evidence for the durable repository transaction journal."""

import ast
from hashlib import sha256
import inspect
import json
from pathlib import Path
from typing import cast

from repoctl.modules.repository_generation.api import (
    CapabilityIntent,
    CapabilityPlan,
    JournalProgress,
    MemoryRepository,
    Operation,
    RepositoryPath,
    begin_journal,
    complete_journal,
    content_digest,
    inspect_journal,
    make_plan,
    record_operation,
    recover_journal,
)


def _operation(*, target: str, content: str) -> Operation:
    return Operation(
        kind="create_product_seed",
        path=RepositoryPath(value=target),
        precondition="absent",
        content=content,
        content_digest=content_digest(content),
    )


def _plan() -> CapabilityPlan:
    return make_plan(
        generator_version="1.0.0",
        base_state_digest="sha256:" + "0" * 64,
        intent=CapabilityIntent(
            schema_version=1,
            name="workflow_execution",
            inbound=("cli", "python"),
            outbound=("clock",),
        ),
        operations=(
            _operation(
                target="src/acme/modules/workflow_execution/ports.py",
                content='"""Boundary vocabulary."""\n',
            ),
            _operation(
                target="src/acme/modules/workflow_execution/api.py",
                content='"""Stable public surface."""\n',
            ),
        ),
        result_state_digest="sha256:" + "1" * 64,
    )


def _document(entry: bytes) -> dict[str, object]:
    value = cast("object", json.loads(entry))
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _stored_state_digest(repository: MemoryRepository, progress: JournalProgress) -> str:
    snapshot = repository.snapshot()
    inspection = repository.inspect_transaction(progress.transaction_id)
    payload = {
        "files": [(file.path.value, file.digest) for file in snapshot.files],
        "transaction": {
            "state": inspection.state,
            "entries": [entry.decode("utf-8") for entry in inspection.entries],
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def test_journal_records_the_plan_operations_and_terminal_completion_marker() -> None:
    plan = _plan()
    repository = MemoryRepository()

    _ = begin_journal(plan, repository)
    for operation in plan.operations:
        _ = record_operation(plan, operation, repository)
    completed = complete_journal(plan, repository)

    inspection = repository.inspect_transaction(completed.transaction_id)
    records = tuple(_document(entry) for entry in inspection.entries)

    assert completed.state == "complete"
    assert inspection.state == "complete"
    assert records[0] == {
        "base_state_digest": plan.base_state_digest,
        "event": "plan",
        "plan_id": plan.plan_id,
        "schema_version": 1,
        "transaction_id": completed.transaction_id,
    }
    assert records[1:-1] == tuple(
        {
            "content_digest": operation.content_digest,
            "event": "operation",
            "kind": operation.kind,
            "path": operation.path.value,
            "precondition": operation.precondition,
            "schema_version": 1,
            "sequence": sequence,
        }
        for sequence, operation in enumerate(plan.operations)
    )
    assert records[-1] == {
        "event": "complete",
        "result_state_digest": plan.result_state_digest,
        "schema_version": 1,
    }


def test_incomplete_journal_names_the_last_recorded_operation() -> None:
    plan = _plan()
    repository = MemoryRepository()

    _ = begin_journal(plan, repository)
    first_operation = plan.operations[0]
    _ = record_operation(plan, first_operation, repository)

    progress = inspect_journal(plan, repository)

    assert progress.state == "incomplete"
    assert progress.recorded_targets == (first_operation.path.value,)
    assert progress.stopped_at == first_operation.path.value
    assert progress.completion_recorded is False


def test_replaying_a_completed_journal_does_not_change_stored_state() -> None:
    plan = _plan()
    repository = MemoryRepository()

    _ = begin_journal(plan, repository)
    for operation in plan.operations:
        _ = record_operation(plan, operation, repository)
    completed = complete_journal(plan, repository)
    before = _stored_state_digest(repository, completed)

    replayed = begin_journal(plan, repository)

    after = _stored_state_digest(repository, replayed)
    assert replayed.state == "complete"
    assert replayed == completed
    assert after == before


def test_recovery_preserves_the_incomplete_journal_classification() -> None:
    plan = _plan()
    repository = MemoryRepository()

    _ = begin_journal(plan, repository)
    first_operation = plan.operations[0]
    _ = record_operation(plan, first_operation, repository)

    recovered = recover_journal(plan, repository)

    assert recovered.state == "recovered"
    assert recovered.recorded_targets == (first_operation.path.value,)
    assert recovered.stopped_at == first_operation.path.value
    assert repository.inspect_transaction(recovered.transaction_id).state == "recovered"


def test_journal_reaches_storage_only_through_the_repository_port() -> None:
    source_path = inspect.getsourcefile(begin_journal)
    assert source_path is not None
    source = Path(source_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=source_path)
    imported_roots = {
        alias.name.partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    port_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "repository"
    }

    assert {"os", "pathlib", "subprocess"}.isdisjoint(imported_roots)
    assert port_calls <= {
        "append_transaction_entry",
        "begin_transaction",
        "complete_transaction",
        "inspect_transaction",
        "recover_transaction",
    }
    assert "RepositoryPort" in source
