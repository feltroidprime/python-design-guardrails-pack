"""Stable public surface of the repository-generation capability."""

from importlib import import_module
from typing import TYPE_CHECKING, cast

from repoctl.modules.repository_generation.adapters.outbound.local_repository import (
    LocalRepository,
)
from repoctl.modules.repository_generation.adapters.outbound.memory_repository import (
    MemoryRepository,
)
from repoctl.modules.repository_generation.application.journal import (
    JournalProgress,
    JournalProtocolError,
    begin_journal,
    complete_journal,
    inspect_journal,
    record_operation,
    recover_journal,
    transaction_id_for,
)
from repoctl.modules.repository_generation.application.ports import (
    RepositoryConflictError,
    RepositoryPathEscapeError,
    RepositoryPort,
    RepositoryPortError,
    RepositoryTransactionError,
    TransactionAlreadyExistsError,
    TransactionInspection,
    TransactionMissingError,
    TransactionState,
    TransactionStateError,
)
from repoctl.modules.repository_generation.domain.decisions import plan
from repoctl.modules.repository_generation.domain.indexes import (
    DerivedCapability,
    DerivedIndexes,
    canonical_index_bytes,
    compile_indexes,
)
from repoctl.modules.repository_generation.domain.intents import (
    CapabilityDeclaration,
    CapabilityIntent,
    CapabilityStatus,
    RepositoryFile,
    RepositoryPath,
    RepositorySnapshot,
)
from repoctl.modules.repository_generation.domain.ownership import (
    AbsolutePathError,
    AmbiguousOwnershipError,
    DotPathSegmentError,
    EmptyPathSegmentError,
    NonCanonicalSeparatorError,
    OwnershipPathError,
    OwnershipRoot,
    OwnershipZone,
    OwnershipZoneRoots,
    ParentPathError,
    RepositoryPathCandidate,
    UnclassifiedPathError,
    UnicodeNormalizationPathError,
    classify_path,
    matching_zones,
    validated_segments,
)
from repoctl.modules.repository_generation.domain.plans import (
    CapabilityPlan,
    Operation,
    canonical_plan_bytes,
    content_digest,
    make_plan,
)
from repoctl.modules.repository_generation.domain.plans_planner import (
    PlanningOwnershipError,
    intended_target_paths,
)
from repoctl.modules.repository_generation.domain.specifications import (
    DeclarationIndexFacts,
    DerivedIndexFacts,
    OwnershipRootFacts,
    classified_path_is_closed,
    derived_indexes_are_exact,
    plan_repetition_is_identical,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Protocol, TextIO

    from repoctl.modules.repository_generation.adapters.inbound.cli_catalog import (
        COMMAND_CATALOG,
        ControlCommandName,
    )

    class _ControlRun(Protocol):
        def __call__(
            self,
            argv: Sequence[str],
            *,
            repository: RepositoryPort,
            out: TextIO,
            err: TextIO,
        ) -> int: ...


def _control_cli_export(name: str) -> object:
    module = import_module("repoctl.modules.repository_generation.adapters.inbound.cli")
    return cast("object", getattr(module, name))


def run(
    argv: Sequence[str],
    *,
    repository: RepositoryPort,
    out: TextIO,
    err: TextIO,
) -> int:
    """Run the repository-control CLI without coupling API import to template rendering."""
    execute = cast("_ControlRun", _control_cli_export("run"))
    return execute(argv, repository=repository, out=out, err=err)


def __getattr__(name: str) -> object:
    """Resolve control-catalog exports only in a rendered generated repository."""
    if name not in {"COMMAND_CATALOG", "ControlCommandName"}:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    catalog = import_module("repoctl.modules.repository_generation.adapters.inbound.cli_catalog")
    return cast("object", getattr(catalog, name))


__all__ = [
    "COMMAND_CATALOG",
    "AbsolutePathError",
    "AmbiguousOwnershipError",
    "CapabilityDeclaration",
    "CapabilityIntent",
    "CapabilityPlan",
    "CapabilityStatus",
    "ControlCommandName",
    "DeclarationIndexFacts",
    "DerivedCapability",
    "DerivedIndexFacts",
    "DerivedIndexes",
    "DotPathSegmentError",
    "EmptyPathSegmentError",
    "JournalProgress",
    "JournalProtocolError",
    "LocalRepository",
    "MemoryRepository",
    "NonCanonicalSeparatorError",
    "Operation",
    "OwnershipPathError",
    "OwnershipRoot",
    "OwnershipRootFacts",
    "OwnershipZone",
    "OwnershipZoneRoots",
    "ParentPathError",
    "PlanningOwnershipError",
    "RepositoryConflictError",
    "RepositoryFile",
    "RepositoryPath",
    "RepositoryPathCandidate",
    "RepositoryPathEscapeError",
    "RepositoryPort",
    "RepositoryPortError",
    "RepositorySnapshot",
    "RepositoryTransactionError",
    "TransactionAlreadyExistsError",
    "TransactionInspection",
    "TransactionMissingError",
    "TransactionState",
    "TransactionStateError",
    "UnclassifiedPathError",
    "UnicodeNormalizationPathError",
    "begin_journal",
    "canonical_index_bytes",
    "canonical_plan_bytes",
    "classified_path_is_closed",
    "classify_path",
    "compile_indexes",
    "complete_journal",
    "content_digest",
    "derived_indexes_are_exact",
    "inspect_journal",
    "intended_target_paths",
    "make_plan",
    "matching_zones",
    "plan",
    "plan_repetition_is_identical",
    "record_operation",
    "recover_journal",
    "run",
    "transaction_id_for",
    "validated_segments",
]
