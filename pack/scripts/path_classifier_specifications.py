"""Independent predicates for repository path classification."""

from unicodedata import normalize

type OwnershipRootFacts = tuple[str, tuple[str, ...]]


def _closed_segments(value: str) -> tuple[str, ...] | None:
    drive_absolute = (
        len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] in "/\\"
    )
    if value.startswith(("/", "\\")) or drive_absolute or "\\" in value:
        return None
    if normalize("NFC", value) != value:
        return None
    segments = tuple(value.split("/"))
    if any(not segment for segment in segments) or ".." in segments or "." in segments:
        return None
    return segments


def _root_contains(root: str, candidate_segments: tuple[str, ...]) -> bool:
    root_segments = _closed_segments(root)
    return root_segments is not None and candidate_segments[: len(root_segments)] == root_segments


def classified_path_is_closed(
    value: str,
    roots: tuple[OwnershipRootFacts, ...],
    result: str,
) -> bool:
    """Judge canonical repository relativity and exact declared ownership."""
    candidate_segments = _closed_segments(value)
    if candidate_segments is None:
        return False
    matches = tuple(
        zone
        for zone, zone_roots in roots
        if any(_root_contains(root, candidate_segments) for root in zone_roots)
    )
    return matches == (result,)
