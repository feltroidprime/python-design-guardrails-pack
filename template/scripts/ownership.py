"""Adapt filesystem-shaped ownership policy to the pure domain classifier."""

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from repoctl.modules.repository_generation.api import (
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
    classify_path as classify_domain_path,
    matching_zones as matching_domain_zones,
    validated_segments,
)

if TYPE_CHECKING:
    from scripts.ownership_policy import OwnershipPolicy

__all__ = [
    "AbsolutePathError",
    "AmbiguousOwnershipError",
    "DotPathSegmentError",
    "EmptyPathSegmentError",
    "NonCanonicalSeparatorError",
    "OwnershipPathError",
    "OwnershipZone",
    "ParentPathError",
    "UnclassifiedPathError",
    "UnicodeNormalizationPathError",
    "classify_path",
    "matching_zones",
    "normalized_relative_path",
]


def _candidate(path: Path) -> RepositoryPathCandidate:
    return RepositoryPathCandidate(value=path.as_posix())


def _domain_zones(policy: OwnershipPolicy) -> tuple[OwnershipZoneRoots, ...]:
    return tuple(
        OwnershipZoneRoots(
            name=OwnershipZone(zone.name),
            roots=tuple(OwnershipRoot(value=root.as_posix()) for root in zone.roots),
        )
        for zone in policy.zones
    )


def normalized_relative_path(path: Path) -> PurePosixPath:
    """Validate one path through the domain owner and expose its segments."""
    return PurePosixPath(*validated_segments(_candidate(path)))


def matching_zones(
    path: Path,
    policy: OwnershipPolicy,
) -> tuple[OwnershipZone, ...]:
    """Delegate ownership matching to the pure domain classifier."""
    return matching_domain_zones(_candidate(path), _domain_zones(policy))


def classify_path(path: Path, policy: OwnershipPolicy) -> OwnershipZone:
    """Delegate sole-owner classification to the pure domain classifier."""
    return classify_domain_path(_candidate(path), _domain_zones(policy))
