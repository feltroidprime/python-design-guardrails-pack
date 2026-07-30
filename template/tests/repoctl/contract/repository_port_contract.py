"""Reusable behavioral contract for repository filesystem implementations.

Adapter tests certify an implementation by subclassing
``RepositoryPortContract`` and supplying fresh ``repository`` and
``escape_path`` fixtures.  The contract deliberately observes only the
application-owned port; an adapter may use a real filesystem, memory, or a
different storage mechanism behind that boundary.
"""

from dataclasses import dataclass
import inspect

import pytest

from repoctl.modules.repository_generation.api import (
    RepositoryConflictError,
    RepositoryPathCandidate,
    RepositoryPathEscapeError,
    RepositoryPort,
    content_digest,
)


@dataclass(frozen=True, slots=True)
class RepositoryPortContractCase:
    """One observable promise and the port operations needed to observe it."""

    identifier: str
    methods: tuple[str, ...]


CONTRACT_CASES = (
    RepositoryPortContractCase(
        identifier="absent-file-creation",
        methods=("write_if_matches", "read_bytes"),
    ),
    RepositoryPortContractCase(
        identifier="compare-and-swap-success",
        methods=("write_if_matches", "read_bytes"),
    ),
    RepositoryPortContractCase(
        identifier="compare-and-swap-conflict",
        methods=("write_if_matches", "read_bytes"),
    ),
    RepositoryPortContractCase(
        identifier="directory-creation",
        methods=("ensure_directory", "write_if_matches", "read_bytes"),
    ),
    RepositoryPortContractCase(
        identifier="normalized-path-handling",
        methods=("write_if_matches", "read_bytes"),
    ),
    RepositoryPortContractCase(
        identifier="symlink-escape-rejection",
        methods=("write_if_matches",),
    ),
    RepositoryPortContractCase(
        identifier="interrupted-transaction-detection",
        methods=("begin_transaction", "append_transaction_entry", "inspect_transaction"),
    ),
    RepositoryPortContractCase(
        identifier="journal-recovery",
        methods=(
            "begin_transaction",
            "append_transaction_entry",
            "inspect_transaction",
            "recover_transaction",
        ),
    ),
    RepositoryPortContractCase(
        identifier="read-after-write-consistency",
        methods=("write_if_matches", "read_bytes", "snapshot"),
    ),
    RepositoryPortContractCase(
        identifier="completed-transaction-state",
        methods=("begin_transaction", "append_transaction_entry", "complete_transaction"),
    ),
)


def repository_port_method_names() -> frozenset[str]:
    """Return the public protocol methods that certified adapters must implement."""
    return frozenset(
        name
        for name, _member in inspect.getmembers(RepositoryPort, inspect.isfunction)
        if not name.startswith("_")
    )


def contract_method_names() -> frozenset[str]:
    """Return every port operation claimed by the reusable contract cases."""
    return frozenset(method for case in CONTRACT_CASES for method in case.methods)


def assert_contract_cases_cover_port_surface() -> None:
    """Fail when the port grows without a behavioral certification case."""
    assert contract_method_names() == repository_port_method_names()


class RepositoryPortContract:
    """Behavior every repository filesystem adapter must exhibit."""

    @pytest.mark.contract
    def test_absent_file_creation(self, repository: RepositoryPort) -> None:
        path = "contract/created.txt"

        candidate = RepositoryPathCandidate(value=path)
        repository.write_if_matches(candidate, b"created", expected_digest="absent")

        assert repository.read_bytes(candidate) == b"created"

    @pytest.mark.contract
    def test_compare_and_swap_succeeds_for_the_current_digest(
        self,
        repository: RepositoryPort,
    ) -> None:
        path = "contract/compare-and-swap.txt"
        candidate = RepositoryPathCandidate(value=path)
        repository.write_if_matches(candidate, b"before", expected_digest="absent")

        repository.write_if_matches(
            candidate,
            b"after",
            expected_digest=content_digest("before"),
        )

        assert repository.read_bytes(candidate) == b"after"

    @pytest.mark.contract
    def test_compare_and_swap_conflict_preserves_existing_bytes(
        self,
        repository: RepositoryPort,
    ) -> None:
        path = "contract/conflict.txt"
        candidate = RepositoryPathCandidate(value=path)
        repository.write_if_matches(candidate, b"before", expected_digest="absent")

        with pytest.raises(RepositoryConflictError):
            repository.write_if_matches(
                candidate,
                b"after",
                expected_digest="sha256:" + "0" * 64,
            )

        assert repository.read_bytes(candidate) == b"before"

    @pytest.mark.contract
    def test_directory_creation_allows_a_nested_write(self, repository: RepositoryPort) -> None:
        repository.ensure_directory(RepositoryPathCandidate(value="contract/nested"))
        path = "contract/nested/value.txt"
        candidate = RepositoryPathCandidate(value=path)

        repository.write_if_matches(candidate, b"nested", expected_digest="absent")

        assert repository.read_bytes(candidate) == b"nested"

    @pytest.mark.contract
    def test_normalized_path_handling_observes_one_file(self, repository: RepositoryPort) -> None:
        normalized = RepositoryPathCandidate(value="contract/normalized/value.txt")
        repository.write_if_matches(
            RepositoryPathCandidate(value="contract/normalized/./value.txt"),
            b"normal",
            expected_digest="absent",
        )

        assert repository.read_bytes(normalized) == b"normal"

    @pytest.mark.contract
    def test_symlink_escape_is_rejected(
        self,
        repository: RepositoryPort,
        escape_path: RepositoryPathCandidate,
    ) -> None:
        with pytest.raises(RepositoryPathEscapeError):
            repository.write_if_matches(escape_path, b"outside", expected_digest="absent")

    @pytest.mark.contract
    def test_interrupted_transaction_is_not_reported_as_complete(
        self,
        repository: RepositoryPort,
    ) -> None:
        transaction_id = "interrupted"
        repository.begin_transaction(transaction_id)
        repository.append_transaction_entry(transaction_id, b'{"sequence":1}')

        inspection = repository.inspect_transaction(transaction_id)

        assert inspection.state == "incomplete"
        assert inspection.entries == (b'{"sequence":1}',)

    @pytest.mark.contract
    def test_journal_recovery_preserves_entries_and_marks_the_transaction_recovered(
        self,
        repository: RepositoryPort,
    ) -> None:
        transaction_id = "recoverable"
        repository.begin_transaction(transaction_id)
        repository.append_transaction_entry(transaction_id, b'{"operation":"create"}')

        recovered = repository.recover_transaction(transaction_id)

        assert recovered.state == "recovered"
        assert recovered.entries == (b'{"operation":"create"}',)
        assert repository.inspect_transaction(transaction_id) == recovered

    @pytest.mark.contract
    def test_read_after_write_is_consistent_with_the_repository_snapshot(
        self,
        repository: RepositoryPort,
    ) -> None:
        path = "contract/snapshot.txt"
        content = b"snapshot"
        candidate = RepositoryPathCandidate(value=path)
        repository.write_if_matches(candidate, content, expected_digest="absent")

        snapshot = repository.snapshot()

        assert repository.read_bytes(candidate) == content
        assert (path, content_digest(content.decode("utf-8"))) in {
            (file.path.value, file.digest) for file in snapshot.files
        }

    @pytest.mark.contract
    def test_completed_transaction_is_reported_as_complete(
        self, repository: RepositoryPort
    ) -> None:
        transaction_id = "complete"
        repository.begin_transaction(transaction_id)
        repository.append_transaction_entry(transaction_id, b'{"sequence":1}')

        repository.complete_transaction(transaction_id)

        assert repository.inspect_transaction(transaction_id).state == "complete"
