"""Pure structural planning from an explicit repository snapshot and intent."""

from hashlib import sha256
import json

from repoctl.modules.repository_generation.domain.indexes import (
    render_derived_indexes,
)
from repoctl.modules.repository_generation.domain.intents import (
    CapabilityDeclaration,
    CapabilityIntent,
    RepositoryPath,
    RepositorySnapshot,
)
from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipPathError,
    OwnershipZone,
    RepositoryPathCandidate,
    classify_path,
)
from repoctl.modules.repository_generation.domain.plans import (
    CapabilityPlan,
    Operation,
    OperationKind,
    content_digest,
    make_plan,
)
from repoctl.modules.repository_generation.domain.specifications import (
    SYSTEM_CAPABILITY_MODULES,
)

GENERATOR_VERSION = "1.0.0"
type IntendedWrite = tuple[RepositoryPath, str]
type FileFacts = tuple[tuple[str, str], ...]


class PlanningOwnershipError(OwnershipPathError):
    """Raised when an intended write belongs to a non-writable ownership zone."""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _state_digest(
    snapshot: RepositorySnapshot,
    declarations: tuple[CapabilityDeclaration, ...],
    files: FileFacts,
) -> str:
    payload = {
        "schema_version": snapshot.schema_version,
        "package": snapshot.package,
        "declarations": [declaration.canonical_payload() for declaration in declarations],
        "files": [{"target": target, "digest": digest} for target, digest in files],
        "ownership": [
            {
                "zone": str(zone.name),
                "roots": [root.value for root in zone.roots],
            }
            for zone in snapshot.ownership_zones
        ],
    }
    return f"sha256:{sha256(_canonical_json_bytes(payload)).hexdigest()}"


def _desired_declaration(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> CapabilityDeclaration:
    existing = next(
        (declaration for declaration in snapshot.declarations if declaration.name == intent.name),
        None,
    )
    module = f"{snapshot.package}.modules.{intent.name}"
    return CapabilityDeclaration(
        name=intent.name,
        python_module=module,
        status=existing.status if existing is not None else "draft",
        proof_catalog=f"proof/modules/{intent.name}.toml",
        inbound=intent.inbound,
        outbound=intent.outbound,
        api=f"{module}.api",
        factory=existing.factory if existing is not None else "",
        cli_catalog=existing.cli_catalog if existing is not None else "",
    )


def _desired_declarations(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> tuple[CapabilityDeclaration, ...]:
    desired = _desired_declaration(snapshot, intent)
    remaining = tuple(
        declaration for declaration in snapshot.declarations if declaration.name != intent.name
    )
    return tuple(sorted((*remaining, desired), key=lambda item: item.name))


def _product_seed_writes(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> tuple[IntendedWrite, ...]:
    base = f"src/{snapshot.package}/modules/{intent.name}"
    api_content = (
        '"""Stable public surface of this product capability."""\n\n'
        + "__all__: tuple[str, ...] = ()\n"
    )
    labels = (
        ("__init__.py", f'"""Product-owned {intent.name} capability."""\n'),
        ("api.py", api_content),
        ("domain/__init__.py", '"""Product domain vocabulary and laws."""\n'),
        ("application/__init__.py", '"""Product use-case orchestration."""\n'),
        ("adapters/__init__.py", '"""Product boundary adapters."""\n'),
        ("adapters/inbound/__init__.py", '"""Inbound product adapters."""\n'),
        ("adapters/outbound/__init__.py", '"""Outbound product adapters."""\n'),
    )
    capability_writes = tuple(
        (RepositoryPath(value=f"{base}/{suffix}"), content) for suffix, content in labels
    )
    proof_content = 'schema_version = 1\nownership_zone = "product"\n'
    return (
        *capability_writes,
        (
            RepositoryPath(value=f"proof/modules/{intent.name}.toml"),
            proof_content,
        ),
    )


def _derived_writes(
    snapshot: RepositorySnapshot,
    declarations: tuple[CapabilityDeclaration, ...],
) -> tuple[IntendedWrite, ...]:
    return render_derived_indexes(
        package=snapshot.package,
        declarations=declarations,
        ownership_zones=snapshot.ownership_zones,
        approved_system_modules=SYSTEM_CAPABILITY_MODULES,
    ).writes


def _all_intended_writes(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> tuple[IntendedWrite, ...]:
    declarations = _desired_declarations(snapshot, intent)
    declaration = _desired_declaration(snapshot, intent)
    writes = (
        *_product_seed_writes(snapshot, intent),
        (
            RepositoryPath(value=f".repo/capabilities/{intent.name}.toml"),
            declaration.canonical_document(),
        ),
        *_derived_writes(snapshot, declarations),
    )
    return tuple(sorted(writes, key=lambda item: item[0].value))


def candidate_targets(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> tuple[RepositoryPath, ...]:
    return tuple(target for target, _content in _all_intended_writes(snapshot, intent))


def _classify(
    snapshot: RepositorySnapshot,
    target: RepositoryPath,
) -> OwnershipZone:
    return classify_path(
        RepositoryPathCandidate(value=target.value),
        snapshot.ownership_zones,
    )


def zone_is_writable(zone: OwnershipZone) -> bool:
    return str(zone) in {"PRODUCT", "DERIVED", "DECLARATION"}


def _selected_writes(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> tuple[tuple[OwnershipZone, RepositoryPath, str], ...]:
    existing = {file.path.value for file in snapshot.files}
    selected: list[tuple[OwnershipZone, RepositoryPath, str]] = []
    for target, content in _all_intended_writes(snapshot, intent):
        zone = _classify(snapshot, target)
        if not zone_is_writable(zone):
            raise PlanningOwnershipError(f"Planning cannot target {zone} ownership: {target.value}")
        if str(zone) == "PRODUCT" and target.value in existing:
            continue
        selected.append((zone, target, content))
    return tuple(selected)


def intended_target_paths(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> tuple[RepositoryPath, ...]:
    """Return the exact canonical target set claimed by the plan."""
    return tuple(target for _zone, target, _content in _selected_writes(snapshot, intent))


def _operation_kind(zone: OwnershipZone) -> OperationKind:
    if str(zone) == "PRODUCT":
        return "create_product_seed"
    if str(zone) == "DECLARATION":
        return "update_declaration"
    if str(zone) == "DERIVED":
        return "write_derived"
    raise PlanningOwnershipError(f"No operation kind writes {zone} ownership.")


def _operations(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> tuple[Operation, ...]:
    prior = {file.path.value: file.digest for file in snapshot.files}
    return tuple(
        Operation(
            kind=_operation_kind(zone),
            path=target,
            precondition=prior.get(target.value, "absent"),
            content=content,
            content_digest=content_digest(content),
        )
        for zone, target, content in _selected_writes(snapshot, intent)
    )


def _result_file_facts(
    snapshot: RepositorySnapshot,
    operations: tuple[Operation, ...],
) -> FileFacts:
    result = {file.path.value: file.digest for file in snapshot.files}
    result.update((item.path.value, item.content_digest) for item in operations)
    return tuple(sorted(result.items()))


def build_plan(
    snapshot: RepositorySnapshot,
    intent: CapabilityIntent,
) -> CapabilityPlan:
    """Build the canonical plan without consulting any ambient state."""
    operations = _operations(snapshot, intent)
    declarations = _desired_declarations(snapshot, intent)
    base_files = tuple((file.path.value, file.digest) for file in snapshot.files)
    return make_plan(
        generator_version=GENERATOR_VERSION,
        base_state_digest=_state_digest(
            snapshot,
            snapshot.declarations,
            base_files,
        ),
        intent=intent,
        operations=operations,
        result_state_digest=_state_digest(
            snapshot,
            declarations,
            _result_file_facts(snapshot, operations),
        ),
    )
