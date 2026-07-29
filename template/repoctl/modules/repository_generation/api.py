"""Stable public surface of the repository-generation capability."""

from repoctl.modules.repository_generation.domain.intents import (
    CapabilityDeclaration,
    CapabilityIntent,
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

__all__ = [
    "CapabilityDeclaration",
    "CapabilityIntent",
    "CapabilityPlan",
    "Operation",
    "RepositoryFile",
    "RepositoryPath",
    "RepositorySnapshot",
    "canonical_plan_bytes",
    "content_digest",
    "make_plan",
]
