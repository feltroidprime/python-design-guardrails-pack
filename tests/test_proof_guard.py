"""Fault-injection tests for the generated repository's closed proof contract."""

from pathlib import Path

from scripts.proof_guard import check


PROOF_TOML = '''
schema_version = 1

[policy]
source_root = "src"
test_root = "verification/tests"
behavior_roots = ["demo.domain"]
excluded_module_stems = ["__init__", "errors", "specifications"]
oracle_module_stems = ["specifications"]

[[properties]]
id = "DEMO-PRESERVES-VALUE"
title = "Identity preserves its explicit value"
statement = "The pure identity decision returns exactly the supplied integer."
scope = "The synchronous identity decision."
assumptions = []
kind = "model"
strength = "normative"
targets = ["demo.domain.decisions:identity"]
oracles = ["demo.domain.specifications:identity_matches"]
evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]
crosshair_targets = ["demo.domain.decisions:identity"]
counterexample = "The result differs from the supplied value."
failure_modes = ["value substitution", "hidden nondeterminism"]
'''

SPECIFICATION = '''
def identity_matches(value: int, result: int) -> bool:
    return value == result
'''

DECISION = '''
import icontract

from demo.domain.specifications import identity_matches


@icontract.ensure(
    lambda value, result: identity_matches(value, result),
    description="PROPERTY[DEMO-PRESERVES-VALUE]: result preserves the input",
)
def identity(value: int) -> int:
    return value
'''

EVIDENCE = '''
from hypothesis import given, strategies as st
import pytest

from demo.domain.decisions import identity
from demo.domain.specifications import identity_matches
from verification.harness.assertions import assert_falsifies, assert_property


@pytest.mark.proves("DEMO-PRESERVES-VALUE")
@given(value=st.integers())
def test_identity_property(value: int) -> None:
    assert_property(
        condition=identity_matches(value, identity(value)),
        property_id="DEMO-PRESERVES-VALUE",
    )


@pytest.mark.falsifies("DEMO-PRESERVES-VALUE")
def test_changed_value_is_a_counterexample() -> None:
    assert_falsifies(
        condition=identity_matches(1, 2),
        property_id="DEMO-PRESERVES-VALUE",
    )
'''


def proof_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src/demo/domain").mkdir(parents=True)
    (root / "verification/tests").mkdir(parents=True)
    (root / "verification/harness").mkdir(parents=True)
    (root / "proof.toml").write_text(PROOF_TOML, encoding="utf-8")
    (root / "src/demo/domain/specifications.py").write_text(
        SPECIFICATION,
        encoding="utf-8",
    )
    (root / "src/demo/domain/decisions.py").write_text(DECISION, encoding="utf-8")
    (root / "verification/tests/test_properties.py").write_text(
        EVIDENCE,
        encoding="utf-8",
    )
    return root


def violation_codes(root: Path) -> set[str]:
    _, violations = check(root)
    return {violation.code for violation in violations}


def test_complete_property_chain_passes(tmp_path: Path) -> None:
    root = proof_project(tmp_path)

    catalog, violations = check(root)

    assert catalog is not None
    assert violations == ()


def test_new_public_core_behavior_is_rejected_until_classified(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decisions = root / "src/demo/domain/decisions.py"
    source = decisions.read_text(encoding="utf-8")
    decisions.write_text(
        f"{source}\n\ndef unclassified(value: int) -> int:\n    return value\n",
        encoding="utf-8",
    )

    assert "PROOF001" in violation_codes(root)


def test_property_target_without_linked_icontract_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
        "def identity(value: int) -> int:\n    return value\n",
        encoding="utf-8",
    )

    codes = violation_codes(root)

    assert "PROOF006" in codes
    assert "PROOF009" in codes


def test_pure_contracted_function_requires_crosshair_evidence(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    manifest = root / "proof.toml"
    manifest.write_text(
        PROOF_TOML.replace(
            'evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]',
            'evidence = ["icontract", "hypothesis", "falsifier"]',
        ).replace(
            'crosshair_targets = ["demo.domain.decisions:identity"]\n',
            "",
        ),
        encoding="utf-8",
    )

    assert "PROOF027" in violation_codes(root)


def test_example_only_evidence_cannot_replace_hypothesis(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    evidence.write_text(
        EVIDENCE.replace("@given(value=st.integers())\n", "").replace(
            "def test_identity_property(value: int) -> None:",
            "def test_identity_property() -> None:",
        ).replace(
            "condition=identity_matches(value, identity(value)),",
            "condition=identity_matches(1, identity(1)),",
        ),
        encoding="utf-8",
    )

    assert "PROOF016" in violation_codes(root)


def test_property_without_falsifying_canary_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    evidence.write_text(EVIDENCE.split("@pytest.mark.falsifies", maxsplit=1)[0], encoding="utf-8")

    assert "PROOF021" in violation_codes(root)


def test_proof_helper_id_must_match_the_marker(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    evidence.write_text(
        EVIDENCE.replace(
            'property_id="DEMO-PRESERVES-VALUE",',
            'property_id="WRONG-PROPERTY-ID",',
            1,
        ),
        encoding="utf-8",
    )

    assert "PROOF012" in violation_codes(root)


def test_oracle_cannot_call_the_behavior_it_judges(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/domain/specifications.py"
    specification.write_text(
        "from demo.domain.decisions import identity\n\n"
        "def identity_matches(value: int, result: int) -> bool:\n"
        "    return identity(value) == result\n",
        encoding="utf-8",
    )

    codes = violation_codes(root)

    assert "PROOF024" in codes
    assert "PROOF025" in codes


def test_oracle_must_be_an_explicit_boolean_predicate(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/domain/specifications.py"
    specification.write_text(
        "def identity_matches(value: int, result: int):\n"
        "    return value == result\n",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)


def test_canonical_proof_must_reference_the_production_target(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    evidence.write_text(
        EVIDENCE.replace(
            "condition=identity_matches(value, identity(value)),",
            "condition=identity_matches(value, value),",
        ),
        encoding="utf-8",
    )

    assert "PROOF026" in violation_codes(root)

CALLABLE_PROPERTY_ID = "CALLABLE-HANDLER-PRESERVES-VALUE"
CALLABLE_TOML = f'''
schema_version = 1

[policy]
source_root = "src"
test_root = "verification/tests"
behavior_roots = ["demo.core"]
excluded_module_stems = ["__init__", "specifications", "callable_target"]
oracle_module_stems = ["specifications"]

[[properties]]
id = "{CALLABLE_PROPERTY_ID}"
title = "Calling the handler preserves its explicit value"
statement = "The callable handler returns exactly the supplied integer."
scope = "The synchronous CreateItem.__call__ method."
assumptions = []
kind = "model"
strength = "normative"
targets = ["demo.core.callable_target:CreateItem.__call__"]
oracles = ["demo.core.specifications:call_matches"]
evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]
crosshair_targets = ["demo.core.callable_target:CreateItem.__call__"]
counterexample = "Construction occurs, but the callable method is never invoked."
failure_modes = ["constructor-only evidence", "ambiguous callable alias"]
'''

CALLABLE_SPECIFICATION = '''
def call_matches(value: int, result: int) -> bool:
    return value == result
'''

CALLABLE_TARGET = f'''
import icontract

from demo.core.specifications import call_matches


class CreateItem:
    @icontract.ensure(
        lambda self, value, result: call_matches(value, result),
        description=(
            "PROPERTY[{CALLABLE_PROPERTY_ID}]: "
            "the call result preserves the explicit input"
        ),
    )
    def __call__(self, value: int) -> int:
        return value
'''

CALLABLE_CANARY = f'''

@pytest.mark.falsifies("{CALLABLE_PROPERTY_ID}")
def test_changed_result_is_a_counterexample() -> None:
    assert_falsifies(
        condition=call_matches(1, 2),
        property_id="{CALLABLE_PROPERTY_ID}",
    )
'''


def callable_evidence(invocation: str) -> str:
    return f'''
from hypothesis import given, strategies as st
import pytest

from demo.core.callable_target import CreateItem
from demo.core.specifications import call_matches
from verification.harness.assertions import assert_falsifies, assert_property


@pytest.mark.proves("{CALLABLE_PROPERTY_ID}")
@given(value=st.integers())
def test_callable_property(value: int) -> None:
{invocation}
    assert_property(
        condition=call_matches(value, result),
        property_id="{CALLABLE_PROPERTY_ID}",
    )
{CALLABLE_CANARY}
'''


def callable_project(tmp_path: Path, invocation: str) -> Path:
    root = tmp_path / "callable-project"
    (root / "src/demo/core").mkdir(parents=True)
    (root / "verification/tests").mkdir(parents=True)
    (root / "verification/harness").mkdir(parents=True)
    (root / "proof.toml").write_text(CALLABLE_TOML, encoding="utf-8")
    (root / "src/demo/core/specifications.py").write_text(
        CALLABLE_SPECIFICATION,
        encoding="utf-8",
    )
    (root / "src/demo/core/callable_target.py").write_text(
        CALLABLE_TARGET,
        encoding="utf-8",
    )
    (root / "verification/tests/test_callable.py").write_text(
        callable_evidence(invocation),
        encoding="utf-8",
    )
    return root


def test_method_target_rejects_constructor_without_call(tmp_path: Path) -> None:
    root = callable_project(
        tmp_path,
        "    handler = CreateItem()\n    result = value",
    )

    assert "PROOF026" in violation_codes(root)


def test_method_target_accepts_immediate_instance_call(tmp_path: Path) -> None:
    root = callable_project(tmp_path, "    result = CreateItem()(value)")

    assert violation_codes(root) == set()


def test_method_target_accepts_assigned_instance_call(tmp_path: Path) -> None:
    root = callable_project(
        tmp_path,
        "    handler = CreateItem()\n    result = handler(value)",
    )

    assert violation_codes(root) == set()


def test_method_target_accepts_explicit_dunder_call(tmp_path: Path) -> None:
    root = callable_project(
        tmp_path,
        "    handler = CreateItem()\n"
        "    result = CreateItem.__call__(handler, value)",
    )

    assert violation_codes(root) == set()


def test_top_level_function_target_remains_recognized(tmp_path: Path) -> None:
    root = proof_project(tmp_path)

    assert violation_codes(root) == set()


def test_ambiguous_callable_alias_does_not_create_false_evidence(tmp_path: Path) -> None:
    root = callable_project(
        tmp_path,
        "    handler = CreateItem()\n"
        "    handler = lambda number: number\n"
        "    result = handler(value)",
    )

    assert "PROOF026" in violation_codes(root)


def test_state_machine_module_tracks_bound_callable_method(tmp_path: Path) -> None:
    root = callable_project(tmp_path, "    result = CreateItem()(value)")
    manifest = root / "proof.toml"
    manifest.write_text(
        CALLABLE_TOML.replace('kind = "model"', 'kind = "state_machine"')
        .replace(
            'evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]',
            'evidence = ["hypothesis-stateful", "falsifier"]',
        )
        .replace(
            'crosshair_targets = ["demo.core.callable_target:CreateItem.__call__"]\n',
            "",
        ),
        encoding="utf-8",
    )
    target = root / "src/demo/core/callable_target.py"
    target.write_text(
        "class CreateItem:\n"
        "    def __call__(self, value: int) -> int:\n"
        "        return value\n",
        encoding="utf-8",
    )
    evidence = root / "verification/tests/test_callable.py"
    evidence.write_text(
        f'''
from hypothesis.stateful import RuleBasedStateMachine, rule, run_state_machine_as_test
import pytest

from demo.core.callable_target import CreateItem
from demo.core.specifications import call_matches
from verification.harness.assertions import assert_falsifies, assert_property


class ReplayMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._handler = CreateItem()

    @rule()
    def step(self) -> None:
        result = self._handler(1)
        assert_property(
            condition=call_matches(1, result),
            property_id="{CALLABLE_PROPERTY_ID}",
        )


@pytest.mark.proves("{CALLABLE_PROPERTY_ID}")
def test_stateful_property() -> None:
    run_state_machine_as_test(ReplayMachine)
{CALLABLE_CANARY}
''',
        encoding="utf-8",
    )

    assert violation_codes(root) == set()


def test_same_named_oracle_from_another_module_is_not_accepted(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    (root / "src/demo/other.py").write_text(
        "def identity_matches(value: int, result: int) -> bool:\n"
        "    return value == result\n",
        encoding="utf-8",
    )
    evidence = root / "verification/tests/test_properties.py"
    evidence.write_text(
        EVIDENCE.replace(
            "from demo.domain.specifications import identity_matches",
            "from demo.other import identity_matches",
        ),
        encoding="utf-8",
    )

    assert "PROOF014" in violation_codes(root)


def test_exact_oracle_import_alias_is_accepted(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    evidence.write_text(
        EVIDENCE.replace(
            "from demo.domain.specifications import identity_matches",
            "from demo.domain.specifications import identity_matches as oracle",
        ).replace("identity_matches(", "oracle("),
        encoding="utf-8",
    )

    assert violation_codes(root) == set()


def stateful_callable_project(tmp_path: Path, machine_source: str) -> Path:
    root = callable_project(tmp_path, "    result = CreateItem()(value)")
    manifest = root / "proof.toml"
    manifest.write_text(
        CALLABLE_TOML.replace('kind = "model"', 'kind = "state_machine"')
        .replace(
            'evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]',
            'evidence = ["hypothesis-stateful", "falsifier"]',
        )
        .replace(
            'crosshair_targets = ["demo.core.callable_target:CreateItem.__call__"]\n',
            "",
        ),
        encoding="utf-8",
    )
    (root / "src/demo/core/callable_target.py").write_text(
        "class CreateItem:\n"
        "    def __call__(self, value: int) -> int:\n"
        "        return value\n",
        encoding="utf-8",
    )
    evidence = root / "verification/tests/test_callable.py"
    evidence.write_text(
        f'''
from hypothesis.stateful import RuleBasedStateMachine, rule, run_state_machine_as_test
import pytest

from demo.core.callable_target import CreateItem
from demo.core.specifications import call_matches
from verification.harness.assertions import assert_falsifies, assert_property


{machine_source}


@pytest.mark.proves("{CALLABLE_PROPERTY_ID}")
def test_stateful_property() -> None:
    run_state_machine_as_test(ReplayMachine)
{CALLABLE_CANARY}
''',
        encoding="utf-8",
    )
    return root


def test_state_machine_dead_method_cannot_supply_proof_evidence(tmp_path: Path) -> None:
    root = stateful_callable_project(
        tmp_path,
        f'''
class ReplayMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._handler = CreateItem()

    @rule()
    def step(self) -> None:
        pass

    def unused_evidence(self) -> None:
        result = self._handler(1)
        assert_property(
            condition=call_matches(1, result),
            property_id="{CALLABLE_PROPERTY_ID}",
        )
''',
    )

    codes = violation_codes(root)

    assert "PROOF014" in codes
    assert "PROOF026" in codes


def test_state_machine_reachable_helper_supplies_proof_evidence(tmp_path: Path) -> None:
    root = stateful_callable_project(
        tmp_path,
        f'''
class ReplayMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._handler = CreateItem()

    @rule()
    def step(self) -> None:
        self._exercise_property()

    def _exercise_property(self) -> None:
        result = self._handler(1)
        assert_property(
            condition=call_matches(1, result),
            property_id="{CALLABLE_PROPERTY_ID}",
        )
''',
    )

    assert violation_codes(root) == set()


def test_state_machine_must_use_a_literal_local_machine_class(tmp_path: Path) -> None:
    root = stateful_callable_project(
        tmp_path,
        f'''
class ReplayMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._handler = CreateItem()

    @rule()
    def step(self) -> None:
        result = self._handler(1)
        assert_property(
            condition=call_matches(1, result),
            property_id="{CALLABLE_PROPERTY_ID}",
        )
''',
    )
    evidence = root / "verification/tests/test_callable.py"
    evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            "run_state_machine_as_test(ReplayMachine)",
            "run_state_machine_as_test(lambda: ReplayMachine)",
        ),
        encoding="utf-8",
    )

    assert "PROOF000" in violation_codes(root)


def test_oracle_cannot_import_or_call_effectful_operations(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/domain/specifications.py"
    specification.write_text(
        "from pathlib import Path\n\n"
        "def identity_matches(value: int, result: int) -> bool:\n"
        "    return Path('state.txt').exists() and value == result\n",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)


def test_oracle_cannot_be_async_or_variadic(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    specification = root / "src/demo/domain/specifications.py"
    specification.write_text(
        "async def identity_matches(*values: int) -> bool:\n"
        "    return len(values) == 2 and values[0] == values[1]\n",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)


def test_missing_declared_target_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    manifest = root / "proof.toml"
    manifest.write_text(
        PROOF_TOML.replace(
            "demo.domain.decisions:identity",
            "demo.domain.decisions:missing_identity",
        ),
        encoding="utf-8",
    )

    assert "PROOF005" in violation_codes(root)


def test_missing_declared_oracle_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    manifest = root / "proof.toml"
    manifest.write_text(
        PROOF_TOML.replace(
            "demo.domain.specifications:identity_matches",
            "demo.domain.specifications:missing_identity_matches",
        ),
        encoding="utf-8",
    )

    assert "PROOF008" in violation_codes(root)


def test_icontract_description_must_carry_a_literal_property_id(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
        DECISION.replace(
            'description="PROPERTY[DEMO-PRESERVES-VALUE]: result preserves the input",',
            'description="result preserves the input",',
        ),
        encoding="utf-8",
    )

    assert "PROOF002" in violation_codes(root)


def test_icontract_property_id_must_exist_in_the_catalog(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
        DECISION.replace("DEMO-PRESERVES-VALUE", "UNKNOWN-PROPERTY"),
        encoding="utf-8",
    )

    assert "PROOF003" in violation_codes(root)


def test_icontract_must_call_a_declared_oracle(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
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
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
        DECISION.replace(
            "@icontract.ensure(\n    lambda value, result: identity_matches(value, result),",
            "def _identity_holds(value: int, result: int) -> bool:\n"
            "    return identity_matches(value, result)\n"
            "\n"
            "\n"
            "@icontract.ensure(\n    _identity_holds,",
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
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
        DECISION.replace(
            "@icontract.ensure(\n    lambda value, result: identity_matches(value, result),",
            "def _identity_holds(value: int, result: int) -> bool:\n"
            "    return value == result\n"
            "\n"
            "\n"
            "@icontract.ensure(\n    _identity_holds,",
        ),
        encoding="utf-8",
    )

    assert "PROOF007" in violation_codes(root)


def test_icontract_rejects_same_named_oracle_from_another_module(
    tmp_path: Path,
) -> None:
    root = proof_project(tmp_path)
    (root / "src/demo/other.py").write_text(
        "def identity_matches(value: int, result: int) -> bool:\n"
        "    return value == result\n",
        encoding="utf-8",
    )
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
        DECISION.replace(
            "from demo.domain.specifications import identity_matches",
            "from demo.other import identity_matches",
        ),
        encoding="utf-8",
    )

    assert "PROOF007" in violation_codes(root)


def test_icontract_accepts_exact_oracle_import_alias(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/domain/decisions.py"
    decision.write_text(
        DECISION.replace(
            "from demo.domain.specifications import identity_matches",
            "from demo.domain.specifications import identity_matches as oracle",
        ).replace("identity_matches(value, result)", "oracle(value, result)"),
        encoding="utf-8",
    )

    assert violation_codes(root) == set()


def test_blank_scope_or_counterexample_is_rejected_by_the_catalog(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    manifest = root / "proof.toml"
    manifest.write_text(
        PROOF_TOML.replace(
            'scope = "The synchronous identity decision."',
            'scope = " "',
        ),
        encoding="utf-8",
    )

    assert "PROOF000" in violation_codes(root)


def test_state_machine_property_requires_the_stateful_runner(tmp_path: Path) -> None:
    root = stateful_callable_project(
        tmp_path,
        f'''
class ReplayMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._handler = CreateItem()

    @rule()
    def step(self) -> None:
        result = self._handler(1)
        assert_property(
            condition=call_matches(1, result),
            property_id="{CALLABLE_PROPERTY_ID}",
        )
''',
    )
    evidence = root / "verification/tests/test_callable.py"
    evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            "    run_state_machine_as_test(ReplayMachine)",
            "    ReplayMachine()",
        ),
        encoding="utf-8",
    )

    assert "PROOF015" in violation_codes(root)


def test_canary_must_use_a_falsifying_helper(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    evidence = root / "verification/tests/test_properties.py"
    source = evidence.read_text(encoding="utf-8")
    canary_start = source.index('@pytest.mark.falsifies("DEMO-PRESERVES-VALUE")')
    evidence.write_text(
        source[:canary_start]
        + source[canary_start:].replace("assert_falsifies(", "assert_property(", 1),
        encoding="utf-8",
    )

    assert "PROOF019" in violation_codes(root)


TWO_ORACLE_SPECIFICATION = '''
def identity_matches(value: int, result: int) -> bool:
    return value == result


def value_is_bounded(value: int) -> bool:
    return -1000 < value < 1000
'''

TWO_ORACLE_PROOF = '''
@pytest.mark.proves("DEMO-PRESERVES-VALUE")
@given(value=st.integers(min_value=-999, max_value=999))
def test_identity_property(value: int) -> None:
    assert_property(
        condition=identity_matches(value, identity(value)) and value_is_bounded(value),
        property_id="DEMO-PRESERVES-VALUE",
    )
'''

CONJOINED_CANARY = '''
@pytest.mark.falsifies("DEMO-PRESERVES-VALUE")
def test_changed_value_is_a_counterexample() -> None:
    assert_falsifies(
        condition=identity_matches(1, 2) and value_is_bounded(5000),
        property_id="DEMO-PRESERVES-VALUE",
    )
'''

SPLIT_CANARIES = '''
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
'''


def two_oracle_project(tmp_path: Path, canaries: str) -> Path:
    root = proof_project(tmp_path)
    (root / "proof.toml").write_text(
        PROOF_TOML.replace(
            'oracles = ["demo.domain.specifications:identity_matches"]',
            'oracles = [\n'
            '  "demo.domain.specifications:identity_matches",\n'
            '  "demo.domain.specifications:value_is_bounded",\n'
            ']',
        ),
        encoding="utf-8",
    )
    (root / "src/demo/domain/specifications.py").write_text(
        TWO_ORACLE_SPECIFICATION,
        encoding="utf-8",
    )
    header, _, _ = EVIDENCE.partition('@pytest.mark.proves("DEMO-PRESERVES-VALUE")')
    (root / "verification/tests/test_properties.py").write_text(
        header.replace(
            "from demo.domain.specifications import identity_matches",
            "from demo.domain.specifications import identity_matches, value_is_bounded",
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


def test_oracle_effect_hidden_behind_a_private_helper_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    (root / "src/demo/domain/specifications.py").write_text(
        "def _recorded(value: int) -> int:\n"
        "    print(value)\n"
        "    return value\n\n\n"
        "def identity_matches(value: int, result: int) -> bool:\n"
        "    return _recorded(value) == result\n",
        encoding="utf-8",
    )

    assert "PROOF023" in violation_codes(root)


EXEMPTED_BEHAVIOR = '\n\ndef unclassified(value: int) -> int:\n    return value\n'


def exempting_project(tmp_path: Path, revisit: str) -> Path:
    root = proof_project(tmp_path)
    decisions = root / "src/demo/domain/decisions.py"
    decisions.write_text(
        decisions.read_text(encoding="utf-8") + EXEMPTED_BEHAVIOR,
        encoding="utf-8",
    )
    (root / "proof.toml").write_text(
        PROOF_TOML
        + "\n[[exemptions]]\n"
        'target = "demo.domain.decisions:unclassified"\n'
        'reason = "Scheduled for a property once the shape settles."\n'
        f'revisit = "{revisit}"\n',
        encoding="utf-8",
    )
    return root


def test_unexpired_exemption_closes_the_surface(tmp_path: Path) -> None:
    root = exempting_project(tmp_path, "2099-01-01")

    _, violations = check(root)

    assert violations == ()


def test_expired_exemption_reopens_the_surface(tmp_path: Path) -> None:
    root = exempting_project(tmp_path, "2000-01-01")

    _, violations = check(root)

    assert [violation.code for violation in violations] == ["PROOF000"]
    assert "expired on 2000-01-01" in violations[0].message
