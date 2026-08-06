"""Require one broad proof per property and one falsifying canary per oracle."""

from collections import Counter
from typing import TYPE_CHECKING

from scripts.proof_guard_model import TestContext, Violation, violation

if TYPE_CHECKING:
    from scripts.proof_catalog import ProofCatalog, PropertySpec
    from scripts.proof_discovery import ProofTest


def _one_marker_id(test: ProofTest) -> str | None:
    ids = (*test.proves_ids, *test.falsifies_ids)
    return ids[0] if len(ids) == 1 else None


def _test_context(
    test: ProofTest,
    catalog: ProofCatalog,
) -> tuple[TestContext | None, list[Violation]]:
    property_id = _one_marker_id(test)
    if property_id is None:
        return None, [
            violation(
                test.path,
                test.line,
                "PROOF010",
                (
                    f"Proof test '{test.name}' needs exactly one @pytest.mark.proves(ID) "
                    "or @pytest.mark.falsifies(ID)."
                ),
            )
        ]
    property_spec = catalog.by_id.get(property_id)
    if property_spec is None:
        return None, [
            violation(
                test.path,
                test.line,
                "PROOF011",
                f"Proof test '{test.name}' references unknown property '{property_id}'.",
            )
        ]
    stateful_proof = property_spec.kind == "state_machine" and bool(test.proves_ids)
    return (
        TestContext(
            property_spec=property_spec,
            helper_names=(test.state_machine_helper_names if stateful_proof else test.helper_names),
            helper_ids=(
                test.state_machine_helper_property_ids
                if stateful_proof
                else test.helper_property_ids
            ),
            invoked_targets=(
                test.state_machine_invoked_targets if stateful_proof else test.invoked_targets
            ),
            has_assertion=(
                test.state_machine_has_assertion if stateful_proof else test.has_assertion
            ),
        ),
        [],
    )


def _helper_link_violations(test: ProofTest, context: TestContext) -> list[Violation]:
    violations: list[Violation] = []
    mismatched = sorted(set(context.helper_ids) - {context.property_id})
    if mismatched:
        violations.append(
            violation(
                test.path,
                test.line,
                "PROOF012",
                (
                    f"Test '{test.name}' is marked '{context.property_id}' but calls proof helpers "
                    f"for: {', '.join(mismatched)}."
                ),
            )
        )
    if context.property_id not in context.helper_ids:
        violations.append(
            violation(
                test.path,
                test.line,
                "PROOF013",
                (
                    f"Test '{test.name}' must pass literal property_id='{context.property_id}' "
                    "to a named proof helper."
                ),
            )
        )
    return violations


def _oracle_reference_violations(
    test: ProofTest,
    context: TestContext,
) -> list[Violation]:
    missing = sorted(set(context.property_spec.oracles) - context.invoked_targets)
    if not missing:
        return []
    return [
        violation(
            test.path,
            test.line,
            "PROOF014",
            f"Test '{test.name}' does not invoke exact declared oracle(s): {', '.join(missing)}.",
        )
    ]


def pinned_oracles(property_spec: PropertySpec, test: ProofTest) -> frozenset[str]:
    """The declared oracles whose truth value this canary's assertion depends on."""
    return frozenset(property_spec.oracles) & test.invoked_targets


def _target_reference_violations(
    test: ProofTest,
    context: TestContext,
) -> list[Violation]:
    missing = sorted(set(context.property_spec.targets) - context.invoked_targets)
    if not missing:
        return []
    return [
        violation(
            test.path,
            test.line,
            "PROOF026",
            f"Canonical proof '{test.name}' does not invoke exact target(s): {', '.join(missing)}.",
        )
    ]


def _proof_engine_violations(
    test: ProofTest,
    context: TestContext,
) -> list[Violation]:
    if context.property_spec.kind == "state_machine":
        if test.uses_state_machine:
            return []
        return [
            violation(
                test.path,
                test.line,
                "PROOF015",
                (
                    f"Proof for state-machine property '{context.property_id}' must call "
                    "run_state_machine_as_test."
                ),
            )
        ]
    if test.uses_hypothesis:
        return []
    return [
        violation(
            test.path,
            test.line,
            "PROOF016",
            f"Broad proof for '{context.property_id}' must use @hypothesis.given.",
        )
    ]


def _proof_assertion_violations(
    test: ProofTest,
    context: TestContext,
) -> list[Violation]:
    violations: list[Violation] = []
    if "assert_property" not in context.helper_names:
        violations.append(
            violation(
                test.path,
                test.line,
                "PROOF017",
                f"Broad proof for '{context.property_id}' must call assert_property.",
            )
        )
    if not context.has_assertion:
        violations.append(
            violation(
                test.path,
                test.line,
                "PROOF018",
                f"Proof test '{test.name}' has no observable oracle/assertion.",
            )
        )
    return violations


def _canonical_proof_violations(
    test: ProofTest,
    context: TestContext,
) -> list[Violation]:
    return [
        *_oracle_reference_violations(test, context),
        *_target_reference_violations(test, context),
        *_proof_engine_violations(test, context),
        *_proof_assertion_violations(test, context),
    ]


def _canary_violations(test: ProofTest, context: TestContext) -> list[Violation]:
    if not {"assert_falsifies", "assert_rejected"} & test.helper_names:
        return [
            violation(
                test.path,
                test.line,
                "PROOF019",
                (
                    f"Canary for '{context.property_id}' must call assert_falsifies "
                    "or assert_rejected."
                ),
            )
        ]
    if "assert_falsifies" not in test.helper_names:
        return []
    pinned = pinned_oracles(context.property_spec, test)
    if len(pinned) == 1:
        return []
    return [
        violation(
            test.path,
            test.line,
            "PROOF028",
            (
                f"Canary '{test.name}' must falsify exactly one declared oracle of "
                f"'{context.property_id}'; a conjunction over {len(pinned)} oracle(s) stays false "
                "when one of them degenerates to a constant."
            ),
        )
    ]


def _test_shape_violations(test: ProofTest, catalog: ProofCatalog) -> list[Violation]:
    context, violations = _test_context(test, catalog)
    if context is None:
        return violations
    violations.extend(_helper_link_violations(test, context))
    if test.proves_ids:
        violations.extend(_canonical_proof_violations(test, context))
    else:
        violations.extend(_canary_violations(test, context))
    return violations


def _property_evidence_count_violations(
    catalog: ProofCatalog,
    property_spec: PropertySpec,
    tests: tuple[ProofTest, ...],
) -> list[Violation]:
    property_id = property_spec.property_id
    proves = sum(property_id in test.proves_ids for test in tests)
    violations: list[Violation] = []
    if proves != 1:
        violations.append(
            violation(
                catalog.path,
                1,
                "PROOF020",
                (
                    f"Property '{property_id}' needs exactly one canonical broad proof; "
                    f"found {proves}."
                ),
            )
        )
    violations.extend(_canary_coverage_violations(catalog, property_spec, tests))
    return violations


def _canary_coverage_violations(
    catalog: ProofCatalog,
    property_spec: PropertySpec,
    tests: tuple[ProofTest, ...],
) -> list[Violation]:
    """Every declared oracle owns a canary, so no single oracle can degenerate unnoticed."""
    pinned: Counter[str] = Counter()
    for test in tests:
        if property_spec.property_id not in test.falsifies_ids:
            continue
        if "assert_falsifies" not in test.helper_names:
            continue
        oracles = pinned_oracles(property_spec, test)
        if len(oracles) == 1:
            pinned.update(oracles)
    return [
        violation(
            catalog.path,
            1,
            "PROOF021",
            (
                f"Oracle '{oracle}' of property '{property_spec.property_id}' needs exactly one "
                f"falsifying canary. Found {pinned[oracle]}. A canary counts only when it meets "
                "four conditions. It is marked @pytest.mark.falsifies for this property. It "
                "calls the assert_falsifies helper, not assert_rejected. It invokes at least "
                "one of the property's declared oracles. It invokes no more than one of them."
            ),
        )
        for oracle in property_spec.oracles
        if pinned[oracle] != 1
    ]


def evidence_coverage_violations(
    catalog: ProofCatalog,
    tests: tuple[ProofTest, ...],
) -> list[Violation]:
    shape_violations = [
        violation for test in tests for violation in _test_shape_violations(test, catalog)
    ]
    count_violations = [
        violation
        for property_spec in catalog.properties
        for violation in _property_evidence_count_violations(catalog, property_spec, tests)
    ]
    return [*shape_violations, *count_violations]
