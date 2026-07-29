import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
import inspect
import json
from pathlib import Path

import icontract
import pytest

from repoctl.modules.repository_generation.api import (
    CapabilityDeclaration,
    CapabilityIntent,
    CapabilityPlan,
    Operation,
    OwnershipRoot,
    OwnershipZone,
    OwnershipZoneRoots,
    RepositoryFile,
    RepositoryPath,
    RepositorySnapshot,
    canonical_plan_bytes,
    content_digest,
    make_plan,
)
from scripts.architecture_policy import load_policy
from scripts.architecture_rules import check_source


def intent(*, inbound: tuple[str, ...] = ("python", "cli")) -> CapabilityIntent:
    return CapabilityIntent(
        schema_version=1,
        name="workflow_execution",
        inbound=inbound,
        outbound=("clock", "store"),
    )


def operation(
    *,
    target: str = "src/acme/modules/workflow_execution/api.py",
    content: str = '"""Stable public surface."""\n',
) -> Operation:
    return Operation(
        kind="create_product_seed",
        path=RepositoryPath(value=target),
        precondition="absent",
        content=content,
        content_digest=content_digest(content),
    )


def plan(*, operations: tuple[Operation, ...] | None = None) -> CapabilityPlan:
    return make_plan(
        generator_version="1.0.0",
        base_state_digest="sha256:" + "0" * 64,
        intent=intent(),
        operations=operations or (operation(),),
        result_state_digest="sha256:" + "1" * 64,
    )


def test_plan_domain_values_are_immutable_slotted_keyword_only_dataclasses() -> None:
    declaration = CapabilityDeclaration(
        name="billing",
        python_module="acme.modules.billing",
        status="draft",
        proof_catalog="proof/modules/billing.toml",
        inbound=("python",),
        outbound=(),
        api="acme.modules.billing.api",
        factory="",
        cli_catalog="",
    )
    repository_path = RepositoryPath(value=".repo/repository.toml")
    file = RepositoryFile(
        path=repository_path,
        digest="sha256:" + "2" * 64,
    )
    snapshot = RepositorySnapshot(
        schema_version=1,
        package="acme",
        declarations=(declaration,),
        files=(file,),
        ownership_zones=(
            OwnershipZoneRoots(
                name=OwnershipZone("FOUNDATION"),
                roots=(OwnershipRoot(value="scripts"),),
            ),
            OwnershipZoneRoots(
                name=OwnershipZone("PRODUCT"),
                roots=(OwnershipRoot(value="src/acme/modules"),),
            ),
            OwnershipZoneRoots(
                name=OwnershipZone("DERIVED"),
                roots=(OwnershipRoot(value="proof/_generated"),),
            ),
            OwnershipZoneRoots(
                name=OwnershipZone("DECLARATION"),
                roots=(OwnershipRoot(value=".repo"),),
            ),
        ),
    )
    values = (intent(), declaration, repository_path, file, snapshot, operation(), plan())

    for value in values:
        value_type = type(value)
        assert is_dataclass(value)
        assert hasattr(value_type, "__slots__")
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in inspect.signature(value_type).parameters.values()
        )
        assert not hasattr(value, "__dict__")
        field = fields(value)[0]
        with pytest.raises(FrozenInstanceError):
            value.__setattr__(field.name, None)


def test_architecture_guard_detects_relaxed_plan_dataclass_policy() -> None:
    root = Path(__file__).resolve().parents[3]
    source = root / "repoctl/modules/repository_generation/domain/plans.py"
    original = source.read_text(encoding="utf-8")
    decorated = "@dataclass(frozen=True, slots=True, kw_only=True)\nclass Operation:"
    without_dataclass = original.replace(decorated, "class Operation:", 1)
    without_frozen = original.replace(
        decorated,
        "@dataclass(slots=True, kw_only=True)\nclass Operation:",
        1,
    )
    policy = load_policy(root)

    missing_codes = {
        item.code
        for item in check_source(
            source,
            without_dataclass,
            ast.parse(without_dataclass, filename=str(source)),
            policy,
        )
    }
    relaxed_codes = {
        item.code
        for item in check_source(
            source,
            without_frozen,
            ast.parse(without_frozen, filename=str(source)),
            policy,
        )
    }

    assert "ARCH006" in missing_codes
    assert "ARCH007" in relaxed_codes


def test_canonical_plan_encoding_and_id_are_content_derived() -> None:
    first = plan()
    same = plan()
    changed = plan(operations=(operation(content='"""Different surface."""\n'),))

    assert canonical_plan_bytes(first) == canonical_plan_bytes(first)
    assert canonical_plan_bytes(first) == canonical_plan_bytes(same)
    assert first.plan_id == same.plan_id
    assert changed.plan_id != first.plan_id
    assert json.loads(canonical_plan_bytes(first))["plan_id"] == first.plan_id


def test_canonical_plan_is_independent_of_input_order_and_locale_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_operation = operation(target="src/acme/modules/workflow_execution/api.py")
    second_operation = operation(
        target="proof/modules/workflow_execution.toml",
        content='schema_version = 1\nownership_zone = "product"\n',
    )
    monkeypatch.setenv("LC_ALL", "C")
    first = make_plan(
        generator_version="1.0.0",
        base_state_digest="sha256:" + "0" * 64,
        intent=intent(inbound=("python", "cli")),
        operations=(first_operation, second_operation),
        result_state_digest="sha256:" + "1" * 64,
    )

    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")
    reordered = make_plan(
        result_state_digest="sha256:" + "1" * 64,
        operations=(second_operation, first_operation),
        intent=intent(inbound=("cli", "python")),
        base_state_digest="sha256:" + "0" * 64,
        generator_version="1.0.0",
    )

    assert canonical_plan_bytes(first) == canonical_plan_bytes(reordered)
    assert first.plan_id == reordered.plan_id


@pytest.mark.parametrize(
    "candidate",
    [
        "/outside.py",
        "src/acme/../outside.py",
    ],
)
def test_operation_rejects_non_repository_relative_paths_with_named_contract(
    candidate: str,
) -> None:
    with pytest.raises(icontract.ViolationError, match="PLAN-PATH-REPOSITORY-RELATIVE"):
        _ = operation(target=candidate)
