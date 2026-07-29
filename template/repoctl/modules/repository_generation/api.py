"""Stable public surface of the repository-generation capability."""

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
from repoctl.modules.repository_generation.domain.plans import (
    CapabilityPlan,
    Operation,
    canonical_plan_bytes,
    content_digest,
    make_plan,
)
from repoctl.modules.repository_generation.domain.specifications import (
    DeclarationIndexFacts,
    DerivedIndexFacts,
    derived_indexes_are_exact,
)

__all__ = [
    "CapabilityDeclaration",
    "CapabilityIntent",
    "CapabilityPlan",
    "CapabilityStatus",
    "DeclarationIndexFacts",
    "DerivedCapability",
    "DerivedIndexFacts",
    "DerivedIndexes",
    "Operation",
    "RepositoryFile",
    "RepositoryPath",
    "RepositorySnapshot",
    "canonical_index_bytes",
    "canonical_plan_bytes",
    "compile_indexes",
    "content_digest",
    "derived_indexes_are_exact",
    "make_plan",
]
