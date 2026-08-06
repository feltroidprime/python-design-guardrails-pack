"""Fault-injection tests for oracle identity, oracle purity and the icontract link.

Each test plants one defect in the tree of `tests.proof_tree` and states the
code the guard must report.
"""

from pathlib import Path

from scripts.proof_guard import check
from tests.proof_tree import (
    DECISION,
    EVIDENCE,
    PROOF_TOML,
    foundation_catalog,
    proof_project,
    violation_codes,
)


def test_oracle_cannot_call_the_behavior_it_judges(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/feature/domain/specifications.py"
    _ = specification.write_text(
        """from demo.feature.domain.decisions import identity

def identity_matches(value: int, result: int) -> bool:
    return identity(value) == result
""",
        encoding="utf-8",
    )

    codes = violation_codes(root)

    assert "PROOF024" in codes
    assert "PROOF025" in codes


def test_oracle_must_be_an_explicit_boolean_predicate(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/feature/domain/specifications.py"
    _ = specification.write_text(
        "def identity_matches(value: int, result: int):\n    return value == result\n",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)


def test_same_named_oracle_from_another_module_is_not_accepted(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    _ = (root / "src/demo/other.py").write_text(
        "def identity_matches(value: int, result: int) -> bool:\n    return value == result\n",
        encoding="utf-8",
    )
    evidence = root / "verification/tests/test_properties.py"
    _ = evidence.write_text(
        EVIDENCE.replace(
            "from demo.feature.domain.specifications import identity_matches",
            "from demo.other import identity_matches",
        ),
        encoding="utf-8",
    )

    assert "PROOF014" in violation_codes(root)


def test_exact_oracle_import_alias_is_accepted(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    _ = evidence.write_text(
        EVIDENCE.replace(
            "from demo.feature.domain.specifications import identity_matches",
            "from demo.feature.domain.specifications import identity_matches as oracle",
        ).replace("identity_matches(", "oracle("),
        encoding="utf-8",
    )

    assert violation_codes(root) == set()


def test_oracle_cannot_import_or_call_effectful_operations(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/feature/domain/specifications.py"
    _ = specification.write_text(
        """from pathlib import Path

def identity_matches(value: int, result: int) -> bool:
    return Path('state.txt').exists() and value == result
""",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)


def test_oracle_cannot_be_async_or_variadic(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/feature/domain/specifications.py"
    _ = specification.write_text(
        """async def identity_matches(*values: int) -> bool:
    return len(values) == 2 and values[0] == values[1]
""",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)


def test_icontract_description_must_carry_a_literal_property_id(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        DECISION.replace(
            'description="PROPERTY[DEMO-PRESERVES-VALUE]: result preserves the input",',
            'description="result preserves the input",',
        ),
        encoding="utf-8",
    )

    assert "PROOF002" in violation_codes(root)


def test_icontract_property_id_must_exist_in_the_catalog(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        DECISION.replace("DEMO-PRESERVES-VALUE", "UNKNOWN-PROPERTY"),
        encoding="utf-8",
    )

    assert "PROOF003" in violation_codes(root)


def test_icontract_must_call_a_declared_oracle(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        DECISION.replace(
            "lambda value, result: identity_matches(value, result)",
            "lambda value, result: value == result",
        ),
        encoding="utf-8",
    )

    assert "PROOF007" in violation_codes(root)


def test_icontract_accepts_a_named_local_condition_calling_the_oracle(
    tmp_path: Path,
) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        DECISION.replace(
            "@icontract.ensure(\n    lambda value, result: identity_matches(value, result),",
            """def _identity_holds(value: int, result: int) -> bool:
    return identity_matches(value, result)


@icontract.ensure(
    _identity_holds,""",
        ),
        encoding="utf-8",
    )

    catalog, violations = check(root)

    assert catalog is not None
    assert violations == ()


def test_icontract_rejects_a_named_local_condition_that_skips_the_oracle(
    tmp_path: Path,
) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        DECISION.replace(
            "@icontract.ensure(\n    lambda value, result: identity_matches(value, result),",
            """def _identity_holds(value: int, result: int) -> bool:
    return value == result


@icontract.ensure(
    _identity_holds,""",
        ),
        encoding="utf-8",
    )

    assert "PROOF007" in violation_codes(root)


def test_icontract_rejects_same_named_oracle_from_another_module(
    tmp_path: Path,
) -> None:
    root = proof_project(tmp_path)
    _ = (root / "src/demo/other.py").write_text(
        "def identity_matches(value: int, result: int) -> bool:\n    return value == result\n",
        encoding="utf-8",
    )
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        DECISION.replace(
            "from demo.feature.domain.specifications import identity_matches",
            "from demo.other import identity_matches",
        ),
        encoding="utf-8",
    )

    assert "PROOF007" in violation_codes(root)


def test_icontract_accepts_exact_oracle_import_alias(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        DECISION.replace(
            "from demo.feature.domain.specifications import identity_matches",
            "from demo.feature.domain.specifications import identity_matches as oracle",
        ).replace("identity_matches(value, result)", "oracle(value, result)"),
        encoding="utf-8",
    )

    assert violation_codes(root) == set()


TWO_ORACLE_SPECIFICATION = """
def identity_matches(value: int, result: int) -> bool:
    return value == result


def value_is_bounded(value: int) -> bool:
    return -1000 < value < 1000
"""

TWO_ORACLE_PROOF = """
@pytest.mark.proves("DEMO-PRESERVES-VALUE")
@given(value=st.integers(min_value=-999, max_value=999))
def test_identity_property(value: int) -> None:
    assert_property(
        condition=identity_matches(value, identity(value)) and value_is_bounded(value),
        property_id="DEMO-PRESERVES-VALUE",
    )
"""

CONJOINED_CANARY = """
@pytest.mark.falsifies("DEMO-PRESERVES-VALUE")
def test_changed_value_is_a_counterexample() -> None:
    assert_falsifies(
        condition=identity_matches(1, 2) and value_is_bounded(5000),
        property_id="DEMO-PRESERVES-VALUE",
    )
"""

SPLIT_CANARIES = """
@pytest.mark.falsifies("DEMO-PRESERVES-VALUE")
def test_changed_value_is_a_counterexample() -> None:
    assert_falsifies(
        condition=identity_matches(1, 2),
        property_id="DEMO-PRESERVES-VALUE",
    )


@pytest.mark.falsifies("DEMO-PRESERVES-VALUE")
def test_out_of_range_value_is_a_counterexample() -> None:
    assert_falsifies(
        condition=value_is_bounded(5000),
        property_id="DEMO-PRESERVES-VALUE",
    )
"""


def two_oracle_project(tmp_path: Path, canaries: str) -> Path:
    root = proof_project(tmp_path)
    _ = foundation_catalog(root).write_text(
        PROOF_TOML.replace(
            'oracles = ["demo.feature.domain.specifications:identity_matches"]',
            """oracles = [
  "demo.feature.domain.specifications:identity_matches",
  "demo.feature.domain.specifications:value_is_bounded",
]""",
        ),
        encoding="utf-8",
    )
    _ = (root / "src/demo/feature/domain/specifications.py").write_text(
        TWO_ORACLE_SPECIFICATION,
        encoding="utf-8",
    )
    header, _, _ = EVIDENCE.partition('@pytest.mark.proves("DEMO-PRESERVES-VALUE")')
    _ = (root / "verification/tests/test_properties.py").write_text(
        header.replace(
            "from demo.feature.domain.specifications import identity_matches",
            "from demo.feature.domain.specifications import identity_matches, value_is_bounded",
        )
        + TWO_ORACLE_PROOF
        + canaries,
        encoding="utf-8",
    )
    return root


def test_canary_conjoining_two_oracles_cannot_pin_either(tmp_path: Path) -> None:
    root = two_oracle_project(tmp_path, CONJOINED_CANARY)

    codes = violation_codes(root)

    assert "PROOF028" in codes
    assert "PROOF021" in codes


def test_one_canary_per_declared_oracle_closes_the_chain(tmp_path: Path) -> None:
    root = two_oracle_project(tmp_path, SPLIT_CANARIES)

    _, violations = check(root)

    assert violations == ()


def test_oracle_effect_hidden_behind_a_private_helper_is_rejected(
    tmp_path: Path,
) -> None:
    root = proof_project(tmp_path)
    _ = (root / "src/demo/feature/domain/specifications.py").write_text(
        """def _recorded(value: int) -> int:
    print(value)
    return value


def identity_matches(value: int, result: int) -> bool:
    return _recorded(value) == result
""",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)
