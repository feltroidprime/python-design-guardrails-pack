"""Certification of the deterministic in-memory repository adapter."""

import inspect

import pytest

from repoctl.modules.repository_generation.api import (
    MemoryRepository,
    RepositoryConflictError,
    RepositoryPathCandidate,
)
from tests.repoctl.contract.repository_port_contract import (
    CONTRACT_CASES,
    RepositoryPortContract,
)

ESCAPE_PATH = RepositoryPathCandidate(value="contract/escape/outside.txt")


class TestMemoryRepository(RepositoryPortContract):
    """Run every shared repository-port case against fresh in-memory state."""

    @pytest.fixture
    def repository(self) -> MemoryRepository:
        return MemoryRepository(escaped_locations=(ESCAPE_PATH,))

    @pytest.fixture
    def escape_path(self) -> RepositoryPathCandidate:
        return ESCAPE_PATH


def _shared_contract_test_names() -> frozenset[str]:
    return frozenset(
        name
        for name, _method in inspect.getmembers(RepositoryPortContract, inspect.isfunction)
        if name.startswith("test_")
    )


@pytest.mark.contract
def test_memory_contract_case_count_equals_the_declared_shared_suite(
    request: pytest.FixtureRequest,
) -> None:
    collected = tuple(
        item
        for item in request.session.items
        if isinstance(item, pytest.Function)
        and item.cls is TestMemoryRepository
        and item.name in _shared_contract_test_names()
    )

    assert len(collected) == len(CONTRACT_CASES)


@pytest.mark.contract
def test_stale_compare_and_swap_preserves_the_stored_value() -> None:
    repository = MemoryRepository()
    path = RepositoryPathCandidate(value="contract/stale.txt")
    repository.write_if_matches(path, b"original", expected_digest="absent")

    with pytest.raises(RepositoryConflictError):
        repository.write_if_matches(
            path,
            b"replacement",
            expected_digest="sha256:" + "0" * 64,
        )

    assert repository.read_bytes(path) == b"original"


def test_default_snapshot_roots_follow_the_configured_package() -> None:
    snapshot = MemoryRepository(package="catalog_service").snapshot()
    roots_by_zone = {
        str(zone.name): {root.value for root in zone.roots} for zone in snapshot.ownership_zones
    }

    assert "src/catalog_service/modules" in roots_by_zone["PRODUCT"]
    assert "src/catalog_service/_generated" in roots_by_zone["DERIVED"]


def test_snapshot_derives_a_capability_declaration_from_memory_contents() -> None:
    declaration = b"""schema_version = 1
name = "alpha"
python_module = "acme.modules.alpha"
status = "draft"
proof_catalog = "proof/modules/alpha.toml"

[boundaries]
inbound = ["python"]
outbound = []

[activation]
api = "acme.modules.alpha.api"
factory = ""
cli_catalog = ""
"""
    repository = MemoryRepository(
        initial_contents={
            RepositoryPathCandidate(value=".repo/capabilities/alpha.toml"): declaration,
        },
    )

    snapshot = repository.snapshot()

    assert [(item.name, item.status, item.api) for item in snapshot.declarations] == [
        ("alpha", "draft", "acme.modules.alpha.api"),
    ]
