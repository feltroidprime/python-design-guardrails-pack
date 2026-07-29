"""Collect explicit repository-control proof tests through the daily proof path."""

from verification.repoctl.test_proof_policy import (
    test_proof_policy_declares_multiroot_discovery_as_data,
)

__all__ = ["test_proof_policy_declares_multiroot_discovery_as_data"]
