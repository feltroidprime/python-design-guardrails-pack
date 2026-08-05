"""Build the trees the proof guard reads: the chain, the callable, the machine.

Every proof-guard test starts from one of these trees and then plants one
defect. `test_crosshair_gate.py` reads the same two catalogs, so the constants
live here rather than in any one test module.
"""

from pathlib import Path

from scripts.proof_guard import check

POLICY_TOML = """
schema_version = 2

[policy]
source_roots = ["src", "."]
test_roots = ["verification/tests"]
behavior_roots = ["domain"]
excluded_module_stems = ["__init__", "errors", "specifications"]
oracle_module_stems = ["specifications"]
"""

CAPABILITY_TOML = """
schema_version = 1
"""

PROOF_TOML = """
schema_version = 1

[[properties]]
id = "DEMO-PRESERVES-VALUE"
title = "Identity preserves its explicit value"
statement = "The pure identity decision returns exactly the supplied integer."
scope = "The synchronous identity decision."
assumptions = []
kind = "model"
strength = "normative"
targets = ["demo.feature.domain.decisions:identity"]
oracles = ["demo.feature.domain.specifications:identity_matches"]
evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]
crosshair_targets = ["demo.feature.domain.decisions:identity"]
counterexample = "The result differs from the supplied value."
failure_modes = ["value substitution", "hidden nondeterminism"]
"""

SPECIFICATION = """
def identity_matches(value: int, result: int) -> bool:
    return value == result
"""

DECISION = """
import icontract

from demo.feature.domain.specifications import identity_matches


@icontract.ensure(
    lambda value, result: identity_matches(value, result),
    description="PROPERTY[DEMO-PRESERVES-VALUE]: result preserves the input",
)
def identity(value: int) -> int:
    return value
"""

EVIDENCE = """
from hypothesis import given, strategies as st
import pytest

from demo.feature.domain.decisions import identity
from demo.feature.domain.specifications import identity_matches
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
"""


def proof_root(root: Path) -> Path:
    """The proof surface is pack-owned; it lives under `pack/proof/`."""
    return root / "pack" / "proof"


def foundation_catalog(root: Path) -> Path:
    return proof_root(root) / "foundation.toml"


def write_policy(root: Path, policy: str = POLICY_TOML) -> None:
    proof_root(root).mkdir(parents=True, exist_ok=True)
    _ = (proof_root(root) / "policy.toml").write_text(policy, encoding="utf-8")


def write_capability_catalog(capability_root: Path) -> None:
    """Rule L1 of #85 gives every capability one `proof.toml`."""
    _ = (capability_root / "proof.toml").write_text(CAPABILITY_TOML, encoding="utf-8")


def proof_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src/demo/feature/domain").mkdir(parents=True)
    (root / "verification/tests").mkdir(parents=True)
    (root / "verification/harness").mkdir(parents=True)
    write_policy(root)
    write_capability_catalog(root / "src/demo/feature")
    _ = foundation_catalog(root).write_text(PROOF_TOML, encoding="utf-8")
    _ = (root / "src/demo/feature/domain/specifications.py").write_text(
        SPECIFICATION,
        encoding="utf-8",
    )
    _ = (root / "src/demo/feature/domain/decisions.py").write_text(DECISION, encoding="utf-8")
    _ = (root / "verification/tests/test_properties.py").write_text(
        EVIDENCE,
        encoding="utf-8",
    )
    return root


def violation_codes(root: Path) -> set[str]:
    _, violations = check(root)
    return {violation.code for violation in violations}


CALLABLE_PROPERTY_ID = "CALLABLE-HANDLER-PRESERVES-VALUE"
CALLABLE_TOML = f'''
schema_version = 1

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

CALLABLE_POLICY_TOML = POLICY_TOML.replace(
    'behavior_roots = ["domain"]', 'behavior_roots = ["core"]'
).replace(
    'excluded_module_stems = ["__init__", "errors", "specifications"]',
    'excluded_module_stems = ["__init__", "specifications", "callable_target"]',
)

CALLABLE_SPECIFICATION = """
def call_matches(value: int, result: int) -> bool:
    return value == result
"""

CALLABLE_TARGET = f"""
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
"""

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
    write_policy(root, CALLABLE_POLICY_TOML)
    write_capability_catalog(root / "src/demo/core")
    _ = foundation_catalog(root).write_text(CALLABLE_TOML, encoding="utf-8")
    _ = (root / "src/demo/core/specifications.py").write_text(
        CALLABLE_SPECIFICATION,
        encoding="utf-8",
    )
    _ = (root / "src/demo/core/callable_target.py").write_text(
        CALLABLE_TARGET,
        encoding="utf-8",
    )
    _ = (root / "verification/tests/test_callable.py").write_text(
        callable_evidence(invocation),
        encoding="utf-8",
    )
    return root


def stateful_callable_project(tmp_path: Path, machine_source: str) -> Path:
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
    _ = (root / "src/demo/core/callable_target.py").write_text(
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


{machine_source}


@pytest.mark.proves("{CALLABLE_PROPERTY_ID}")
def test_stateful_property() -> None:
    run_state_machine_as_test(ReplayMachine)
{CALLABLE_CANARY}
''',
        encoding="utf-8",
    )
    return root
