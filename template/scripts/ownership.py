"""Classify repository-relative paths from the declared ownership roots."""

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from scripts.ownership_policy import OwnershipPolicy


OwnershipZone = NewType("OwnershipZone", str)


class OwnershipPathError(ValueError):
    """Base class for invalid ownership-classification inputs."""


class AbsolutePathError(OwnershipPathError):
    """Raised when a path is not repository-relative."""


class ParentPathError(OwnershipPathError):
    """Raised when a path tries to escape the repository with ``..``."""


class UnclassifiedPathError(OwnershipPathError):
    """Raised when no declared ownership root contains a path."""


class AmbiguousOwnershipError(OwnershipPathError):
    """Raised when roots from more than one zone contain a path."""


def normalized_relative_path(path: Path) -> PurePosixPath:
    """Validate and normalize a repository-relative path without accessing the filesystem."""
    if path.is_absolute():
        raise AbsolutePathError(f"Ownership paths must be repository-relative: {path}")
    if ".." in path.parts:
        raise ParentPathError(f"Ownership paths must not contain '..': {path}")
    return PurePosixPath(*path.parts)


def _contains(root: PurePosixPath, path: PurePosixPath) -> bool:
    return path == root or root in path.parents


def matching_zones(path: Path, policy: OwnershipPolicy) -> tuple[OwnershipZone, ...]:
    """Return all declared zones containing ``path`` in declaration order."""
    normalized = normalized_relative_path(path)
    return tuple(
        OwnershipZone(zone.name)
        for zone in policy.zones
        if any(_contains(root, normalized) for root in zone.roots)
    )


def classify_path(path: Path, policy: OwnershipPolicy) -> OwnershipZone:
    """Return one ownership zone or reject an invalid, unknown, or ambiguous path."""
    zones = matching_zones(path, policy)
    if not zones:
        raise UnclassifiedPathError(f"No ownership root contains: {path}")
    if len(zones) > 1:
        names = ", ".join(zones)
        raise AmbiguousOwnershipError(f"Multiple ownership zones contain {path}: {names}")
    return next(iter(zones))
