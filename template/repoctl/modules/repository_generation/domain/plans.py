"""Immutable operations and canonical, content-addressed capability plans."""

from dataclasses import dataclass, fields
from hashlib import sha256
import json
from typing import Literal, cast, override

import icontract

from repoctl.modules.repository_generation.domain.intents import (
    CapabilityIntent,
    RepositoryPath,
)
from repoctl.modules.repository_generation.domain.specifications import (
    digest_is_valid,
    file_paths_are_unique,
    operation_kind_is_valid,
    plan_path_is_repository_relative,
    precondition_is_valid,
    schema_version_is_supported,
)

type OperationKind = Literal[
    "create_product_seed",
    "update_declaration",
    "write_derived",
]


def content_digest(content: str) -> str:
    """Return the stable identity of UTF-8 plan content."""
    return f"sha256:{sha256(content.encode('utf-8')).hexdigest()}"


def _operation_kind_holds(self: object) -> bool:
    return operation_kind_is_valid(cast("Operation", self).kind)


def _operation_path_holds(self: object) -> bool:
    return plan_path_is_repository_relative(cast("Operation", self).path.value)


def _operation_precondition_holds(self: object) -> bool:
    return precondition_is_valid(cast("Operation", self).precondition)


def _operation_content_holds(self: object) -> bool:
    operation = cast("Operation", self)
    return operation.content_digest == content_digest(operation.content)


@icontract.invariant(
    _operation_kind_holds,
    description="PLAN-OPERATION-KIND-KNOWN: operation kind must be supported",
)
@icontract.invariant(
    _operation_path_holds,
    description="PLAN-PATH-REPOSITORY-RELATIVE: operation paths must not escape the repository",
)
@icontract.invariant(
    _operation_precondition_holds,
    description="PLAN-PRECONDITION-VALID: operation precondition must be absent or a digest",
)
@icontract.invariant(
    _operation_content_holds,
    description="PLAN-CONTENT-DIGEST-MATCHES: operation content must match its digest",
)
@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """One intended write, its exact content, and its required prior state."""

    kind: OperationKind
    path: RepositoryPath
    precondition: str
    content: str
    content_digest: str

    @override
    def __getstate__(self) -> list[object]:
        """Keep slotted invariant-bearing values copyable for symbolic execution."""
        return [getattr(self, field.name, None) for field in fields(self)]

    def __setstate__(self, state: list[object]) -> None:
        """Restore a copied value through the frozen dataclass boundary."""
        for field, value in zip(fields(self), state, strict=True):
            object.__setattr__(self, field.name, value)


def _intent_payload(intent: CapabilityIntent) -> dict[str, object]:
    return {
        "schema_version": intent.schema_version,
        "name": intent.name,
        "inbound": list(intent.inbound),
        "outbound": list(intent.outbound),
    }


def _operation_payload(operation: Operation) -> dict[str, object]:
    return {
        "kind": operation.kind,
        "path": operation.path.value,
        "precondition": operation.precondition,
        "content": operation.content,
        "content_digest": operation.content_digest,
    }


def _ordered_operations(operations: tuple[Operation, ...]) -> tuple[Operation, ...]:
    return tuple(
        sorted(
            operations,
            key=lambda operation: (
                operation.path.value,
                operation.kind,
                operation.precondition,
                operation.content_digest,
            ),
        )
    )


def _plan_payload(
    *,
    schema_version: int,
    generator_version: str,
    base_state_digest: str,
    intent: CapabilityIntent,
    operations: tuple[Operation, ...],
    result_state_digest: str,
    plan_id: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "generator_version": generator_version,
        "base_state_digest": base_state_digest,
        "intent": _intent_payload(intent),
        "operations": [_operation_payload(operation) for operation in operations],
        "result_state_digest": result_state_digest,
    }
    if plan_id is not None:
        payload["plan_id"] = plan_id
    return payload


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _derived_plan_id(
    *,
    schema_version: int,
    generator_version: str,
    base_state_digest: str,
    intent: CapabilityIntent,
    operations: tuple[Operation, ...],
    result_state_digest: str,
) -> str:
    payload = _plan_payload(
        schema_version=schema_version,
        generator_version=generator_version,
        base_state_digest=base_state_digest,
        intent=intent,
        operations=operations,
        result_state_digest=result_state_digest,
        plan_id=None,
    )
    return f"sha256:{sha256(_canonical_json_bytes(payload)).hexdigest()}"


def _plan_id_matches(self: object) -> bool:
    plan = cast("CapabilityPlan", self)
    return plan.plan_id == _derived_plan_id(
        schema_version=plan.schema_version,
        generator_version=plan.generator_version,
        base_state_digest=plan.base_state_digest,
        intent=plan.intent,
        operations=plan.operations,
        result_state_digest=plan.result_state_digest,
    )


def _plan_schema_holds(self: object) -> bool:
    return schema_version_is_supported(cast("CapabilityPlan", self).schema_version)


def _plan_generator_holds(self: object) -> bool:
    return bool(cast("CapabilityPlan", self).generator_version)


def _plan_digests_hold(self: object) -> bool:
    plan = cast("CapabilityPlan", self)
    return digest_is_valid(plan.base_state_digest) and digest_is_valid(plan.result_state_digest)


def _plan_targets_hold(self: object) -> bool:
    plan = cast("CapabilityPlan", self)
    return file_paths_are_unique(
        tuple(operation.path.value for operation in plan.operations)
    )


@icontract.invariant(
    _plan_schema_holds,
    description="PLAN-SCHEMA-SUPPORTED: plan schema version must be supported",
)
@icontract.invariant(
    _plan_generator_holds,
    description="PLAN-GENERATOR-VERSION-PRESENT: generator version must be explicit",
)
@icontract.invariant(
    _plan_digests_hold,
    description="PLAN-STATE-DIGESTS-VALID: plan state digests must be SHA-256 identifiers",
)
@icontract.invariant(
    _plan_targets_hold,
    description="PLAN-TARGETS-UNIQUE: a plan must name each target path once",
)
@icontract.invariant(
    _plan_id_matches,
    description="PLAN-ID-CONTENT-DERIVED: plan ID must match its canonical content",
)
@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityPlan:
    """A versioned, deterministic, inspectable set of intended writes."""

    schema_version: int
    plan_id: str
    generator_version: str
    base_state_digest: str
    intent: CapabilityIntent
    operations: tuple[Operation, ...]
    result_state_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "operations", _ordered_operations(self.operations))

    @override
    def __getstate__(self) -> list[object]:
        """Keep slotted invariant-bearing values copyable for symbolic execution."""
        return [getattr(self, field.name, None) for field in fields(self)]

    def __setstate__(self, state: list[object]) -> None:
        """Restore a copied value through the frozen dataclass boundary."""
        for field, value in zip(fields(self), state, strict=True):
            object.__setattr__(self, field.name, value)


def make_plan(
    *,
    generator_version: str,
    base_state_digest: str,
    intent: CapabilityIntent,
    operations: tuple[Operation, ...],
    result_state_digest: str,
) -> CapabilityPlan:
    """Construct a plan whose ID is derived from its canonical content."""
    ordered = _ordered_operations(operations)
    schema_version = 1
    plan_id = _derived_plan_id(
        schema_version=schema_version,
        generator_version=generator_version,
        base_state_digest=base_state_digest,
        intent=intent,
        operations=ordered,
        result_state_digest=result_state_digest,
    )
    return CapabilityPlan(
        schema_version=schema_version,
        plan_id=plan_id,
        generator_version=generator_version,
        base_state_digest=base_state_digest,
        intent=intent,
        operations=ordered,
        result_state_digest=result_state_digest,
    )


def canonical_plan_bytes(plan: CapabilityPlan) -> bytes:
    """Encode a plan as locale-independent canonical UTF-8 JSON."""
    return _canonical_json_bytes(
        _plan_payload(
            schema_version=plan.schema_version,
            generator_version=plan.generator_version,
            base_state_digest=plan.base_state_digest,
            intent=plan.intent,
            operations=plan.operations,
            result_state_digest=plan.result_state_digest,
            plan_id=plan.plan_id,
        )
    )
