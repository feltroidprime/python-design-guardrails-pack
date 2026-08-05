from pathlib import Path

import pytest

from scripts.architecture_policy import derive_package
from scripts.identity import discover_capabilities
from scripts.proof_catalog import load_catalog


@pytest.mark.proof
def test_proof_policy_declares_discovery_roots_as_data() -> None:
    root = Path(__file__).resolve().parents[3]
    policy = load_catalog(root).policy
    source_roots = tuple(path.relative_to(root) for path in policy.source_roots)
    test_roots = tuple(path.relative_to(root) for path in policy.test_roots)

    assert source_roots == (Path("src"), Path("pack"))
    assert test_roots == (Path("pack/verification"),)


@pytest.mark.proof
def test_the_policy_takes_the_package_from_the_tree() -> None:
    """The policy is pack-owned, so the package comes from the tree, not the file."""
    root = Path(__file__).resolve().parents[3]
    package = derive_package(root / "src")
    text = (root / "pack" / "proof" / "policy.toml").read_text(encoding="utf-8")

    assert package not in text


@pytest.mark.proof
def test_a_behavior_root_names_one_layer_of_one_capability() -> None:
    """Mandatory proof coverage is product behavior, so it follows the capabilities."""
    root = Path(__file__).resolve().parents[3]
    package = derive_package(root / "src")
    capabilities = discover_capabilities(root, package)
    policy = load_catalog(root).policy

    assert policy.behavior_roots == tuple(
        f"{package}.{capability}.{layer}"
        for capability in capabilities
        for layer in ("domain", "application")
    )
