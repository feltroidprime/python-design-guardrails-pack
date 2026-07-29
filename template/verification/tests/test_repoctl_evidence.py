"""Collect explicit repository-control proof tests through the daily proof path."""

from verification.repoctl.test_derived_index_properties import (
    test_a_draft_entry_is_a_real_index_counterexample,
    test_compilation_is_byte_stable_for_the_same_declaration_set,
    test_compiled_membership_is_exactly_the_active_subset,
    test_compiler_cannot_perform_runtime_module_discovery,
)
from verification.repoctl.test_path_closed_properties import (
    test_absolute_paths_raise_a_named_error,
    test_empty_segments_raise_a_named_error,
    test_named_path_errors_share_one_boundary_type,
    test_parent_escapes_raise_a_named_error,
    test_script_facade_has_no_second_classification_implementation,
    test_successful_classification_is_closed,
    test_unicode_normalization_variants_raise_a_named_error,
    test_wrong_zone_is_a_real_path_closure_counterexample,
)
from verification.repoctl.test_plan_deterministic_properties import (
    test_different_plan_bytes_are_a_real_determinism_counterexample,
    test_same_snapshot_and_intent_produce_identical_plan_bytes,
)
from verification.repoctl.test_proof_policy import (
    test_proof_policy_declares_multiroot_discovery_as_data,
)

__all__ = [
    "test_a_draft_entry_is_a_real_index_counterexample",
    "test_absolute_paths_raise_a_named_error",
    "test_compilation_is_byte_stable_for_the_same_declaration_set",
    "test_compiled_membership_is_exactly_the_active_subset",
    "test_compiler_cannot_perform_runtime_module_discovery",
    "test_different_plan_bytes_are_a_real_determinism_counterexample",
    "test_empty_segments_raise_a_named_error",
    "test_named_path_errors_share_one_boundary_type",
    "test_parent_escapes_raise_a_named_error",
    "test_proof_policy_declares_multiroot_discovery_as_data",
    "test_same_snapshot_and_intent_produce_identical_plan_bytes",
    "test_script_facade_has_no_second_classification_implementation",
    "test_successful_classification_is_closed",
    "test_unicode_normalization_variants_raise_a_named_error",
    "test_wrong_zone_is_a_real_path_closure_counterexample",
]
