"""Fault-injection tests for callable method targets and stateful evidence.

Each test plants one defect in the callable tree of `tests.proof_tree` and
states the code the guard must report.
"""

from pathlib import Path

from tests.proof_tree import (
    CALLABLE_CANARY,
    CALLABLE_PROPERTY_ID,
    CALLABLE_TOML,
    callable_project,
    foundation_catalog,
    stateful_callable_project,
    violation_codes,
)


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
        "    handler = CreateItem()\n    result = CreateItem.__call__(handler, value)",
    )

    assert violation_codes(root) == set()


def test_ambiguous_callable_alias_does_not_create_false_evidence(
    tmp_path: Path,
) -> None:
    root = callable_project(
        tmp_path,
        """    handler = CreateItem()
    handler = lambda number: number
    result = handler(value)""",
    )

    assert "PROOF026" in violation_codes(root)


def test_state_machine_module_tracks_bound_callable_method(tmp_path: Path) -> None:
    root = callable_project(tmp_path, "    result = CreateItem()(value)")
    manifest = foundation_catalog(root)
    _ = manifest.write_text(
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
    _ = target.write_text(
        "class CreateItem:\n    def __call__(self, value: int) -> int:\n        return value\n",
        encoding="utf-8",
    )
    evidence = root / "verification/tests/test_callable.py"
    _ = evidence.write_text(
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
    _ = evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            "run_state_machine_as_test(ReplayMachine)",
            "run_state_machine_as_test(lambda: ReplayMachine)",
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
    _ = evidence.write_text(
        evidence.read_text(encoding="utf-8").replace(
            "    run_state_machine_as_test(ReplayMachine)",
            "    ReplayMachine()",
        ),
        encoding="utf-8",
    )

    assert "PROOF015" in violation_codes(root)
