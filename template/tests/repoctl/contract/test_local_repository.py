"""Certification of the real local-filesystem repository adapter."""

import inspect
from pathlib import Path

import pytest

from repoctl.modules.repository_generation.api import (
    LocalRepository,
    RepositoryPathCandidate,
    RepositoryPathEscapeError,
)
from tests.repoctl.contract.repository_port_contract import (
    CONTRACT_CASES,
    RepositoryPortContract,
)
from tests.repoctl.contract.test_memory_repository import (
    TestMemoryRepository as _TestMemoryRepository,
)


def _outside_symlink_path(root: Path) -> RepositoryPathCandidate:
    outside = root.parent / f"{root.name}-outside"
    outside.mkdir()
    link = root / "contract" / "escape"
    link.parent.mkdir()
    link.symlink_to(outside, target_is_directory=True)
    return RepositoryPathCandidate(value="contract/escape/outside.txt")


class TestLocalRepository(RepositoryPortContract):
    """Run every shared repository-port case against a real temporary directory."""

    @pytest.fixture
    def repository(self, tmp_path: Path) -> LocalRepository:
        return LocalRepository(root=tmp_path)

    @pytest.fixture
    def escape_path(self, tmp_path: Path) -> RepositoryPathCandidate:
        return _outside_symlink_path(tmp_path)


def _shared_contract_test_names(
    implementation: type[RepositoryPortContract],
) -> frozenset[str]:
    return frozenset(
        name
        for name, _method in inspect.getmembers(implementation, inspect.isfunction)
        if name.startswith("test_")
    )


@pytest.mark.contract
def test_local_contract_case_count_matches_the_memory_implementation(
    request: pytest.FixtureRequest,
) -> None:
    collected = tuple(
        item
        for item in request.session.items
        if isinstance(item, pytest.Function)
        and item.cls is TestLocalRepository
        and item.name in _shared_contract_test_names(TestLocalRepository)
    )

    memory_case_names = _shared_contract_test_names(_TestMemoryRepository)

    assert len(collected) == len(memory_case_names)
    assert len(collected) == len(CONTRACT_CASES)


@pytest.mark.contract
def test_real_symlink_escape_is_rejected_with_the_named_port_error(tmp_path: Path) -> None:
    repository = LocalRepository(root=tmp_path)
    escape_path = _outside_symlink_path(tmp_path)

    with pytest.raises(RepositoryPathEscapeError):
        repository.write_if_matches(escape_path, b"outside", expected_digest="absent")


@pytest.mark.contract
def test_truncated_journal_is_reported_incomplete_not_complete(tmp_path: Path) -> None:
    repository = LocalRepository(root=tmp_path)
    transaction_id = "interrupted"
    repository.begin_transaction(transaction_id)
    repository.append_transaction_entry(transaction_id, b'{"sequence":1}')

    transaction_directory = tmp_path / ".repo" / "transactions"
    (journal_path,) = tuple(transaction_directory.iterdir())
    _ = journal_path.write_bytes(journal_path.read_bytes()[:-5])

    inspection = repository.inspect_transaction(transaction_id)

    assert inspection.state == "incomplete"
    assert inspection.state != "complete"
