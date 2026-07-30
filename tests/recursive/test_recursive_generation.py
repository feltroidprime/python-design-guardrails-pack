"""Recursive template → N0 → N1 → N2 acceptance evidence."""

import ast
from pathlib import Path

import pytest

from tests.recursive.harness import (
    REPOCTL_PREFIX,
    ShapeFixture,
    assert_no_invented_business_logic,
    run_recursive_walk,
)

PACKAGE = "recursive_project"
PROPERTY_ID = "ALPHA::NON-NEGATIVE"
EXPECTED_STEPS = (
    "render N0",
    "bootstrap N0",
    "validate repository-generation as a system capability",
    "run repo capabilities",
    "plan capability alpha",
    "apply capability alpha",
    "assert alpha contains no invented business logic",
    "add a minimal real alpha implementation from a test fixture",
    "add alpha properties and evidence",
    "activate alpha",
    "run prove-one for alpha",
    "run the full gate",
    "plan and apply capability beta from the resulting N1 repository",
    "verify alpha's product bytes are unchanged",
    "activate beta",
    "retire alpha",
    "verify alpha's files remain unchanged",
    "verify derived runtime indexes contain beta but not alpha",
    "run the full gate again",
)


def _write_fixture_file(repository: Path, relative: str, content: str) -> None:
    target = repository / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_text(content, encoding="utf-8")


class AlphaFixture:
    """Small proof-carrying behavior used only by the recursive acceptance test."""

    property_id = PROPERTY_ID

    def install_implementation(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None:
        module = f"{package}.modules.{capability}"
        _write_fixture_file(
            repository,
            f"src/{package}/modules/{capability}/domain/specifications.py",
            """\
def result_is_non_negative(result: int) -> bool:
    return result >= 0
""",
        )
        _write_fixture_file(
            repository,
            f"src/{package}/modules/{capability}/domain/non_negative.py",
            f"""\
import icontract

from {module}.domain.specifications import result_is_non_negative


def _result_is_non_negative(result: int) -> bool:
    return result_is_non_negative(result)


@icontract.ensure(
    _result_is_non_negative,
    description="PROPERTY[{PROPERTY_ID}]: result is non-negative",
)
def non_negative(value: int) -> int:
    return max(0, value)
""",
        )
        _write_fixture_file(
            repository,
            f"src/{package}/modules/{capability}/api.py",
            f'''\
"""Stable public surface of the alpha test capability."""

from {module}.domain.non_negative import non_negative
from {module}.domain.specifications import result_is_non_negative

__all__ = ["non_negative", "result_is_non_negative"]
''',
        )

    def install_evidence(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None:
        module = f"{package}.modules.{capability}"
        _write_fixture_file(
            repository,
            f"proof/modules/{capability}.toml",
            f'''\
schema_version = 1
ownership_zone = "product"

[[properties]]
id = "{PROPERTY_ID}"
title = "Alpha results are non-negative"
statement = "The alpha operation maps every integer to a non-negative integer."
scope = "The pure alpha operation over one integer."
assumptions = []
kind = "invariant"
strength = "normative"
targets = ["{module}.domain.non_negative:non_negative"]
oracles = ["{module}.domain.specifications:result_is_non_negative"]
evidence = ["icontract", "hypothesis", "crosshair", "falsifier"]
crosshair_targets = ["{module}.domain.non_negative:non_negative"]
counterexample = "The operation returns a negative integer."
failure_modes = ["negative result"]
''',
        )
        _write_fixture_file(
            repository,
            f"verification/modules/{capability}/test_alpha_fixture.py",
            f'''\
"""Proof evidence injected by the pack's recursive acceptance fixture."""

from hypothesis import given, strategies as st
import pytest

from {module}.api import non_negative, result_is_non_negative
from verification.harness.assertions import assert_falsifies, assert_property


@pytest.mark.proof
@pytest.mark.proves("{PROPERTY_ID}")
@given(st.integers())
def test_alpha_results_are_non_negative(value: int) -> None:
    result = non_negative(value)

    assert_property(
        condition=result_is_non_negative(result),
        property_id="{PROPERTY_ID}",
    )


@pytest.mark.proof
@pytest.mark.falsifies("{PROPERTY_ID}")
def test_negative_result_is_a_real_counterexample() -> None:
    assert_falsifies(
        condition=result_is_non_negative(-1),
        property_id="{PROPERTY_ID}",
    )
''',
        )


def test_recursive_walk_executes_the_specification_through_repoctl(
    tmp_path: Path,
) -> None:
    recursive_walk = run_recursive_walk(tmp_path / "recursive-project", AlphaFixture())

    assert recursive_walk.steps == EXPECTED_STEPS
    assert recursive_walk.runtime_capabilities == ("beta",)
    creation_invocations = tuple(
        invocation
        for invocation in recursive_walk.invocations
        if invocation[: len(REPOCTL_PREFIX)] == REPOCTL_PREFIX
        and invocation[len(REPOCTL_PREFIX) : len(REPOCTL_PREFIX) + 2]
        in {("capability", "plan"), ("capability", "apply")}
    )

    assert len(creation_invocations) == 4
    assert all(
        invocation[: len(REPOCTL_PREFIX)] == REPOCTL_PREFIX for invocation in creation_invocations
    )


def test_harness_has_no_direct_product_write_primitive() -> None:
    harness_source = Path(run_recursive_walk.__code__.co_filename).read_text(encoding="utf-8")
    tree = ast.parse(harness_source)
    direct_writes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"mkdir", "open", "touch", "write_bytes", "write_text"}
    }

    assert direct_writes == set()
    assert ShapeFixture.__doc__ is not None


@pytest.mark.parametrize(
    "forbidden_source",
    ["NotImplementedError", "class InvoiceEntity:", "assert True"],
)
def test_fresh_capability_business_logic_check_is_load_bearing(
    tmp_path: Path,
    forbidden_source: str,
) -> None:
    capability = tmp_path / "alpha"
    capability.mkdir()
    _ = (capability / "api.py").write_text(forbidden_source, encoding="utf-8")

    with pytest.raises(AssertionError, match="invented business logic"):
        assert_no_invented_business_logic(capability)
