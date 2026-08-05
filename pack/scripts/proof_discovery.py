"""Stable facade for proof target, oracle, and property-test discovery."""

from scripts.proof_model import (
    ContractLink,
    DiscoveryError,
    OracleShape,
    ProofTest,
    SourceTarget,
)
from scripts.proof_sources import (
    discover_behavior_targets,
    discover_oracle,
    discover_target,
)
from scripts.proof_tests import discover_tests

__all__ = [
    "ContractLink",
    "DiscoveryError",
    "OracleShape",
    "ProofTest",
    "SourceTarget",
    "discover_behavior_targets",
    "discover_oracle",
    "discover_target",
    "discover_tests",
]
