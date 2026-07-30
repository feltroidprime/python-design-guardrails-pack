"""Collect explicit repository-control proof tests through the daily proof path."""

from verification.repoctl.test_derived_index_properties import (
    test_a_draft_entry_is_a_real_index_counterexample,
    test_compilation_is_byte_stable_for_the_same_declaration_set,
    test_compiled_membership_is_exactly_the_active_subset,
    test_compiler_cannot_perform_runtime_module_discovery,
)
from verification.repoctl.test_lifecycle_state_machine import (
    test_activation_requires_current_complete_evidence,
    test_activation_without_refusal_is_a_real_counterexample,
    test_changed_product_bytes_are_a_real_retirement_counterexample,
    test_each_missing_activation_requirement_is_named_in_the_refusal,
    test_reactivating_a_retired_capability_requires_current_evidence,
    test_retirement_preserves_product_files,
    test_transition_module_exposes_no_delete_or_purge_callable,
    test_transition_refuses_a_declaration_path_owned_as_product,
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
    test_proof_policy_declares_discovery_roots_as_data,
)

__all__ = [
    "test_a_draft_entry_is_a_real_index_counterexample",
    "test_absolute_paths_raise_a_named_error",
    "test_activation_requires_current_complete_evidence",
    "test_activation_without_refusal_is_a_real_counterexample",
    "test_changed_product_bytes_are_a_real_retirement_counterexample",
    "test_compilation_is_byte_stable_for_the_same_declaration_set",
    "test_compiled_membership_is_exactly_the_active_subset",
    "test_compiler_cannot_perform_runtime_module_discovery",
    "test_different_plan_bytes_are_a_real_determinism_counterexample",
    "test_each_missing_activation_requirement_is_named_in_the_refusal",
    "test_empty_segments_raise_a_named_error",
    "test_named_path_errors_share_one_boundary_type",
    "test_parent_escapes_raise_a_named_error",
    "test_proof_policy_declares_discovery_roots_as_data",
    "test_reactivating_a_retired_capability_requires_current_evidence",
    "test_retirement_preserves_product_files",
    "test_same_snapshot_and_intent_produce_identical_plan_bytes",
    "test_script_facade_has_no_second_classification_implementation",
    "test_successful_classification_is_closed",
    "test_transition_module_exposes_no_delete_or_purge_callable",
    "test_transition_refuses_a_declaration_path_owned_as_product",
    "test_unicode_normalization_variants_raise_a_named_error",
    "test_wrong_zone_is_a_real_path_closure_counterexample",
]
