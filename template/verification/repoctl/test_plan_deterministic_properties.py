"""Properties for pure deterministic repository capability planning."""

import ast
from collections.abc import Iterable
import inspect
from pathlib import Path

from hypothesis import given, strategies as st
import pytest

from repoctl.modules.repository_generation import api
from repoctl.modules.repository_generation.api import (
    CapabilityDeclaration,
    CapabilityIntent,
    OwnershipRoot,
    OwnershipZone,
    OwnershipZoneRoots,
    PlanningOwnershipError,
    RepositoryFile,
    RepositoryPath,
    RepositorySnapshot,
    canonical_plan_bytes,
    intended_target_paths,
    plan,
    plan_repetition_is_identical,
)
from scripts.architecture_policy import load_policy
from scripts.architecture_rules import check_source
from verification.harness.assertions import assert_falsifies, assert_property

ZERO_DIGEST = "sha256:" + "0" * 64
ONE_DIGEST = "sha256:" + "1" * 64
EXPECTED_TARGETS = frozenset(
    {
        ".repo/capabilities/planned_capability.toml",
        "proof/_generated/index.json",
        "proof/modules/planned_capability.toml",
        "src/acme/_generated/active_capabilities.py",
        "src/acme/_generated/cli_catalog.py",
        "src/acme/_generated/composition.py",
        "src/acme/modules/planned_capability/__init__.py",
        "src/acme/modules/planned_capability/adapters/__init__.py",
        "src/acme/modules/planned_capability/adapters/inbound/__init__.py",
        "src/acme/modules/planned_capability/adapters/outbound/__init__.py",
        "src/acme/modules/planned_capability/api.py",
        "src/acme/modules/planned_capability/application/__init__.py",
        "src/acme/modules/planned_capability/domain/__init__.py",
    }
)


def _ownership(*, reverse: bool = False) -> tuple[OwnershipZoneRoots, ...]:
    zones = (
        OwnershipZoneRoots(
            name=OwnershipZone("FOUNDATION"),
            roots=(OwnershipRoot(value="scripts"),),
        ),
        OwnershipZoneRoots(
            name=OwnershipZone("PRODUCT"),
            roots=(
                OwnershipRoot(value="src/acme/modules"),
                OwnershipRoot(value="proof/modules"),
                OwnershipRoot(value="tests/modules"),
                OwnershipRoot(value="verification/modules"),
                OwnershipRoot(value="docs/product"),
            ),
        ),
        OwnershipZoneRoots(
            name=OwnershipZone("DERIVED"),
            roots=(
                OwnershipRoot(value="src/acme/_generated"),
                OwnershipRoot(value="proof/_generated"),
                OwnershipRoot(value="docs/architecture/generated"),
            ),
        ),
        OwnershipZoneRoots(
            name=OwnershipZone("DECLARATION"),
            roots=(OwnershipRoot(value=".repo"),),
        ),
    )
    if not reverse:
        return zones
    return tuple(
        OwnershipZoneRoots(name=zone.name, roots=tuple(reversed(zone.roots)))
        for zone in reversed(zones)
    )


def _declaration(index: int) -> CapabilityDeclaration:
    name = f"existing_{index:03d}"
    module = f"acme.modules.{name}"
    return CapabilityDeclaration(
        name=name,
        python_module=module,
        status=("draft", "active", "retired")[index % 3],
        proof_catalog=f"proof/modules/{name}.toml",
        inbound=("python",),
        outbound=(),
        api=f"{module}.api",
        factory="",
        cli_catalog="",
    )


def _intent() -> CapabilityIntent:
    return CapabilityIntent(
        schema_version=1,
        name="planned_capability",
        inbound=("python", "cli"),
        outbound=("clock", "store"),
    )


def _snapshot(
    count: int,
    *,
    files: Iterable[RepositoryFile] = (),
    reverse: bool = False,
) -> RepositorySnapshot:
    declarations = tuple(_declaration(index) for index in range(count))
    if reverse:
        declarations = tuple(reversed(declarations))
    return RepositorySnapshot(
        schema_version=1,
        package="acme",
        declarations=declarations,
        files=tuple(reversed(tuple(files))) if reverse else tuple(files),
        ownership_zones=_ownership(reverse=reverse),
    )


@pytest.mark.proof
@pytest.mark.proves("REPOCTL::PLAN-DETERMINISTIC")
@given(existing_count=st.integers(min_value=0, max_value=100))
def test_same_snapshot_and_intent_produce_identical_plan_bytes(
    existing_count: int,
) -> None:
    snapshot = _snapshot(existing_count)
    intent = _intent()

    first = plan(snapshot, intent)
    repeated = plan(snapshot, intent)
    first_bytes = canonical_plan_bytes(first)
    repeated_bytes = canonical_plan_bytes(repeated)

    assert_property(
        condition=plan_repetition_is_identical(
            first_bytes,
            repeated_bytes,
            first.plan_id,
            repeated.plan_id,
        ),
        property_id="REPOCTL::PLAN-DETERMINISTIC",
    )
    assert first_bytes == repeated_bytes
    assert first.plan_id == repeated.plan_id


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::PLAN-DETERMINISTIC")
def test_different_plan_bytes_are_a_real_determinism_counterexample() -> None:
    assert_falsifies(
        condition=plan_repetition_is_identical(
            b'{"plan":"first"}',
            b'{"plan":"second"}',
            ZERO_DIGEST,
            ONE_DIGEST,
        ),
        property_id="REPOCTL::PLAN-DETERMINISTIC",
    )


@given(existing_count=st.integers(min_value=0, max_value=100))
def test_operations_exactly_cover_claimed_targets_with_preconditions(
    existing_count: int,
) -> None:
    declaration_target = RepositoryPath(value=".repo/capabilities/planned_capability.toml")
    derived_target = RepositoryPath(value="proof/_generated/index.json")
    files = (
        RepositoryFile(path=declaration_target, digest=ZERO_DIGEST),
        RepositoryFile(path=derived_target, digest=ONE_DIGEST),
    )
    snapshot = _snapshot(existing_count, files=files)

    result = plan(snapshot, _intent())

    operations_by_target = {operation.path.value: operation for operation in result.operations}
    claimed_targets = {target.value for target in intended_target_paths(snapshot, _intent())}
    assert claimed_targets == EXPECTED_TARGETS
    assert set(operations_by_target) == claimed_targets
    assert all(operation.precondition for operation in result.operations)
    assert operations_by_target[declaration_target.value].precondition == ZERO_DIGEST
    assert operations_by_target[derived_target.value].precondition == ONE_DIGEST
    assert {
        operation.kind
        for target, operation in operations_by_target.items()
        if target.startswith(("src/acme/modules/", "proof/modules/"))
    } == {"create_product_seed"}
    assert {
        operation.kind
        for target, operation in operations_by_target.items()
        if target.startswith(".repo/")
    } == {"update_declaration"}
    assert {
        operation.kind
        for target, operation in operations_by_target.items()
        if target.startswith(("src/acme/_generated/", "proof/_generated/"))
    } == {"write_derived"}


def test_existing_product_seed_is_never_a_plan_operation() -> None:
    product_target = RepositoryPath(value="src/acme/modules/planned_capability/api.py")
    snapshot = _snapshot(
        0,
        files=(RepositoryFile(path=product_target, digest=ZERO_DIGEST),),
    )

    result = plan(snapshot, _intent())

    assert product_target.value not in {operation.path.value for operation in result.operations}
    assert product_target not in intended_target_paths(snapshot, _intent())


def test_planning_ignores_cwd_environment_and_snapshot_enumeration_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    existing_count = 100
    other_directory = tmp_path / "other"
    other_directory.mkdir()
    files = (
        RepositoryFile(
            path=RepositoryPath(value=".repo/repository.toml"),
            digest=ZERO_DIGEST,
        ),
        RepositoryFile(
            path=RepositoryPath(value="proof/_generated/index.json"),
            digest=ONE_DIGEST,
        ),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REPOCTL_UNRELATED", "first")
    first = plan(_snapshot(existing_count, files=files), _intent())

    monkeypatch.chdir(other_directory)
    monkeypatch.setenv("REPOCTL_UNRELATED", "second")
    reordered = plan(
        _snapshot(existing_count, files=files, reverse=True),
        _intent(),
    )

    assert canonical_plan_bytes(first) == canonical_plan_bytes(reordered)
    assert first.plan_id == reordered.plan_id


def test_planner_domain_rejects_a_deliberate_os_import() -> None:
    source_path = inspect.getsourcefile(PlanningOwnershipError)
    assert source_path is not None
    path = Path(source_path)
    source = path.read_text(encoding="utf-8")
    policy = load_policy(path.parents[4])
    clean_codes = {
        item.code
        for item in check_source(
            path,
            source,
            ast.parse(source, filename=str(path)),
            policy,
        )
    }
    mutation = "import os\n" + source
    mutation_codes = {
        item.code
        for item in check_source(
            path,
            mutation,
            ast.parse(mutation, filename=str(path)),
            policy,
        )
    }

    assert "ARCH011" not in clean_codes
    assert "ARCH011" in mutation_codes


def test_planner_symbols_are_exposed_only_through_the_capability_api() -> None:
    assert api.plan is plan
    assert api.intended_target_paths is intended_target_paths
