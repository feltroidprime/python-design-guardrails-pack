from pathlib import Path

import pytest

from scripts.proof_catalog import load_catalog


@pytest.mark.proof
def test_proof_policy_declares_discovery_roots_as_data() -> None:
    root = Path(__file__).resolve().parents[2]
    policy = load_catalog(root).policy
    source_roots = tuple(path.relative_to(root) for path in policy.source_roots)
    test_roots = tuple(path.relative_to(root) for path in policy.test_roots)

    assert source_roots == (Path("src"), Path())
    assert test_roots == (Path("verification"),)
