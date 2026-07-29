"""Collect explicit repository-control proof tests through the daily proof path."""

from verification.repoctl.test_derived_index_properties import (
    test_a_draft_entry_is_a_real_index_counterexample,
    test_compilation_is_byte_stable_for_the_same_declaration_set,
    test_compiled_membership_is_exactly_the_active_subset,
    test_compiler_cannot_perform_runtime_module_discovery,
)
from verification.repoctl.test_proof_policy import (
    test_proof_policy_declares_multiroot_discovery_as_data,
)

__all__ = [
    "test_a_draft_entry_is_a_real_index_counterexample",
    "test_compilation_is_byte_stable_for_the_same_declaration_set",
    "test_compiled_membership_is_exactly_the_active_subset",
    "test_compiler_cannot_perform_runtime_module_discovery",
    "test_proof_policy_declares_multiroot_discovery_as_data",
]
