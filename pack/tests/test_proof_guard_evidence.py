"""Fault-injection tests for the Hypothesis evidence and the canary rules.

Each test plants one defect in the tree of `tests.proof_tree` and states the
code the guard must report.
"""

from pathlib import Path

from tests.proof_tree import (
    EVIDENCE,
    PROOF_TOML,
    foundation_catalog,
    proof_project,
    violation_codes,
)


def test_pure_contracted_function_requires_crosshair_evidence(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    manifest = foundation_catalog(root)
    _ = manifest.write_text(
        PROOF_TOML.replace(
            'evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]',
            'evidence = ["icontract", "hypothesis", "falsifier"]',
        ).replace(
            'crosshair_targets = ["demo.feature.domain.decisions:identity"]\n',
            "",
        ),
        encoding="utf-8",
    )

    assert "PROOF027" in violation_codes(root)


def test_example_only_evidence_cannot_replace_hypothesis(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    _ = evidence.write_text(
        EVIDENCE.replace("@given(value=st.integers())\n", "")
        .replace(
            "def test_identity_property(value: int) -> None:",
            "def test_identity_property() -> None:",
        )
        .replace(
            "condition=identity_matches(value, identity(value)),",
            "condition=identity_matches(1, identity(1)),",
        ),
        encoding="utf-8",
    )

    assert "PROOF016" in violation_codes(root)


def test_property_without_falsifying_canary_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    _ = evidence.write_text(
        EVIDENCE.split("@pytest.mark.falsifies", maxsplit=1)[0], encoding="utf-8"
    )

    assert "PROOF021" in violation_codes(root)


def test_proof_helper_id_must_match_the_marker(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    _ = evidence.write_text(
        EVIDENCE.replace(
            'property_id="DEMO-PRESERVES-VALUE",',
            'property_id="WRONG-PROPERTY-ID",',
            1,
        ),
        encoding="utf-8",
    )

    assert "PROOF012" in violation_codes(root)


def test_canonical_proof_must_reference_the_production_target(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    _ = evidence.write_text(
        EVIDENCE.replace(
            "condition=identity_matches(value, identity(value)),",
            "condition=identity_matches(value, value),",
        ),
        encoding="utf-8",
    )

    assert "PROOF026" in violation_codes(root)


def test_canary_must_use_a_falsifying_helper(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    source = evidence.read_text(encoding="utf-8")
    canary_start = source.index('@pytest.mark.falsifies("DEMO-PRESERVES-VALUE")')
    _ = evidence.write_text(
        source[:canary_start]
        + source[canary_start:].replace("assert_falsifies(", "assert_property(", 1),
        encoding="utf-8",
    )

    assert "PROOF019" in violation_codes(root)
