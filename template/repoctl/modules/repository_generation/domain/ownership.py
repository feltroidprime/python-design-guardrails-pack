"""Pure repository path normalization and ownership classification."""

from dataclasses import dataclass
from typing import NewType
from unicodedata import normalize

import icontract

from repoctl.modules.repository_generation.domain.specifications import (
    OwnershipRootFacts,
    classified_path_is_closed,
)

OwnershipZone = NewType("OwnershipZone", str)


class OwnershipPathError(ValueError):
    """Base class for rejected ownership-classification inputs."""


class AbsolutePathError(OwnershipPathError):
    """Raised when a path is not repository-relative."""


class ParentPathError(OwnershipPathError):
    """Raised when a path tries to escape the repository with ``..``."""


class EmptyPathSegmentError(OwnershipPathError):
    """Raised when a path contains a blank segment."""


class UnicodeNormalizationPathError(OwnershipPathError):
    """Raised when path text is not in canonical NFC form."""


class NonCanonicalSeparatorError(OwnershipPathError):
    """Raised when a path uses a non-POSIX separator."""


class DotPathSegmentError(OwnershipPathError):
    """Raised when a path contains a redundant current-directory segment."""


class UnclassifiedPathError(OwnershipPathError):
    """Raised when no declared ownership root contains a path."""


class AmbiguousOwnershipError(OwnershipPathError):
    """Raised when roots from more than one zone contain a path."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RepositoryPathCandidate:
    """Untrusted path text retained exactly until classification."""

    value: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnershipRoot:
    """One canonical repository-relative root from declared policy."""

    value: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnershipZoneRoots:
    """The roots explicitly assigned to one ownership zone."""

    name: OwnershipZone
    roots: tuple[OwnershipRoot, ...]


def _is_absolute(value: str) -> bool:
    drive_absolute = (
        len(value) >= 3
        and value[0].isalpha()
        and value[1] == ":"
        and value[2] in "/\\"
    )
    return value.startswith(("/", "\\")) or drive_absolute


def validated_segments(candidate: RepositoryPathCandidate) -> tuple[str, ...]:
    """Return canonical segments or raise one named boundary error."""
    value = candidate.value
    if _is_absolute(value):
        raise AbsolutePathError(f"Ownership paths must be repository-relative: {value}")
    if "\\" in value:
        raise NonCanonicalSeparatorError(
            f"Ownership paths must use POSIX separators: {value}"
        )
    if normalize("NFC", value) != value:
        raise UnicodeNormalizationPathError(
            f"Ownership paths must use canonical NFC text: {value}"
        )
    segments = tuple(value.split("/"))
    if any(not segment for segment in segments):
        raise EmptyPathSegmentError(f"Ownership paths must not contain empty segments: {value}")
    if ".." in segments:
        raise ParentPathError(f"Ownership paths must not contain '..': {value}")
    if "." in segments:
        raise DotPathSegmentError(f"Ownership paths must not contain '.': {value}")
    return segments


def _contains(root: OwnershipRoot, candidate_segments: tuple[str, ...]) -> bool:
    root_segments = validated_segments(RepositoryPathCandidate(value=root.value))
    return candidate_segments[: len(root_segments)] == root_segments


def matching_zones(
    candidate: RepositoryPathCandidate,
    zones: tuple[OwnershipZoneRoots, ...],
) -> tuple[OwnershipZone, ...]:
    """Return all declared zones containing a canonical candidate."""
    candidate_segments = validated_segments(candidate)
    return tuple(
        zone.name
        for zone in zones
        if any(_contains(root, candidate_segments) for root in zone.roots)
    )


def _root_facts(
    zones: tuple[OwnershipZoneRoots, ...],
) -> tuple[OwnershipRootFacts, ...]:
    return tuple(
        (str(zone.name), tuple(root.value for root in zone.roots)) for zone in zones
    )


def _classification_is_closed(
    candidate: RepositoryPathCandidate,
    zones: tuple[OwnershipZoneRoots, ...],
    result: OwnershipZone,
) -> bool:
    return classified_path_is_closed(
        candidate.value,
        _root_facts(zones),
        str(result),
    )


def _classification_input_is_closed(
    candidate: RepositoryPathCandidate,
    zones: tuple[OwnershipZoneRoots, ...],
) -> bool:
    facts = _root_facts(zones)
    return any(
        classified_path_is_closed(candidate.value, facts, zone)
        for zone, _roots in facts
    )


def _classification_input_error(
    candidate: RepositoryPathCandidate,
    zones: tuple[OwnershipZoneRoots, ...],
) -> OwnershipPathError:
    try:
        matches = matching_zones(candidate, zones)
    except OwnershipPathError as error:
        return error
    if not matches:
        return UnclassifiedPathError(
            f"No ownership root contains: {candidate.value}"
        )
    names = ", ".join(matches)
    return AmbiguousOwnershipError(
        f"Multiple ownership zones contain {candidate.value}: {names}"
    )


@icontract.require(
    _classification_input_is_closed,
    description="classification input has exactly one canonical declared owner",
    error=_classification_input_error,
)
@icontract.ensure(
    _classification_is_closed,
    description="PROPERTY[REPOCTL::PLAN-PATH-CLOSED]",
)
def classify_path(
    candidate: RepositoryPathCandidate,
    zones: tuple[OwnershipZoneRoots, ...],
) -> OwnershipZone:
    """Return the sole declared owner or reject an unclosed path."""
    matches = matching_zones(candidate, zones)
    if not matches:
        raise UnclassifiedPathError(f"No ownership root contains: {candidate.value}")
    if len(matches) > 1:
        names = ", ".join(matches)
        raise AmbiguousOwnershipError(
            f"Multiple ownership zones contain {candidate.value}: {names}"
        )
    return next(iter(matches))
