"""Collection and surface-coverage checks for the repository port contract."""

import pytest

from tests.repoctl.contract.repository_port_contract import (
    CONTRACT_CASES,
    assert_contract_cases_cover_port_surface,
)


@pytest.mark.contract
def test_repository_port_contract_covers_every_protocol_method() -> None:
    assert_contract_cases_cover_port_surface()
    assert {case.identifier for case in CONTRACT_CASES} >= {
        "absent-file-creation",
        "compare-and-swap-success",
        "compare-and-swap-conflict",
        "directory-creation",
        "normalized-path-handling",
        "symlink-escape-rejection",
        "interrupted-transaction-detection",
        "journal-recovery",
        "read-after-write-consistency",
    }


@pytest.mark.contract
@pytest.mark.parametrize("_implementation", [])
def test_repository_port_contract_is_collected_before_an_adapter_is_certified(
    _implementation: object,
) -> None:
    """Reserve a visible skipped contract case until an adapter inherits the suite."""
