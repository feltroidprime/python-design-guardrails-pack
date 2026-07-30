"""Independent predicates for repository-generation domain values."""

import re
from unicodedata import normalize

SCHEMA_VERSION = 1
SYSTEM_CAPABILITY_MODULES: tuple[tuple[str, str], ...] = (
    ("repository_generation", "repoctl.modules.repository_generation"),
)
CAPABILITY_NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
LIFECYCLE_STATUSES = frozenset({"draft", "active", "retired"})
OWNERSHIP_ZONES = frozenset({"FOUNDATION", "PRODUCT", "DERIVED", "DECLARATION"})
OPERATION_KINDS = frozenset(
    {
        "create_product_seed",
        "update_declaration",
        "write_derived",
    }
)


def schema_version_is_supported(value: int) -> bool:
    """Return whether ``value`` is the sole schema version understood here."""
    return value == SCHEMA_VERSION


def capability_name_is_valid(value: str) -> bool:
    """Return whether ``value`` is canonical lowercase snake case."""
    return CAPABILITY_NAME.fullmatch(value) is not None


def lifecycle_status_is_valid(value: str) -> bool:
    """Return whether ``value`` belongs to the closed lifecycle vocabulary."""
    return value in LIFECYCLE_STATUSES


def digest_is_valid(value: str) -> bool:
    """Return whether ``value`` is a lowercase SHA-256 identifier."""
    return DIGEST.fullmatch(value) is not None


def strings_are_canonical(values: tuple[str, ...]) -> bool:
    """Return whether strings are unique and sorted by Unicode code point."""
    return values == tuple(sorted(set(values)))


def plan_path_is_repository_relative(value: str) -> bool:
    """Reject the path escapes that a plan value can recognize without policy data."""
    parts = value.split("/")
    return bool(value) and not value.startswith("/") and ".." not in parts


def declaration_names_are_unique(values: tuple[str, ...]) -> bool:
    """Return whether a snapshot names each declaration once."""
    return len(values) == len(set(values))


def file_paths_are_unique(values: tuple[str, ...]) -> bool:
    """Return whether a snapshot or plan names each target path once."""
    return len(values) == len(set(values))


def ownership_zone_names_are_complete(values: tuple[str, ...]) -> bool:
    """Return whether the explicit snapshot owns each canonical zone once."""
    return len(values) == len(set(values)) and frozenset(values) == OWNERSHIP_ZONES


def operation_kind_is_valid(value: str) -> bool:
    """Return whether ``value`` belongs to the closed plan-operation vocabulary."""
    return value in OPERATION_KINDS


def precondition_is_valid(value: str) -> bool:
    """Return whether a write expects absence or one exact prior digest."""
    return value == "absent" or digest_is_valid(value)


type DeclarationIndexFacts = tuple[
    str,
    str,
    str,
    str,
    tuple[str, ...],
    tuple[str, ...],
    str,
    str,
    str,
]
type DerivedIndexFacts = tuple[
    str,
    str,
    str,
    tuple[str, ...],
    tuple[str, ...],
    str,
    str,
    str,
]


def _active_index_facts(
    declaration: DeclarationIndexFacts,
) -> DerivedIndexFacts | None:
    (
        name,
        status,
        python_module,
        proof_catalog,
        inbound,
        outbound,
        api,
        factory,
        cli_catalog,
    ) = declaration
    if status != "active":
        return None
    return (
        name,
        python_module,
        proof_catalog,
        inbound,
        outbound,
        api,
        factory,
        cli_catalog,
    )


def derived_indexes_are_exact(
    declarations: tuple[DeclarationIndexFacts, ...],
    derived: tuple[DerivedIndexFacts, ...],
) -> bool:
    """Judge exact, duplicate-free, canonical active-declaration membership."""
    expected = frozenset(
        projected
        for declaration in declarations
        if (projected := _active_index_facts(declaration)) is not None
    )
    return (
        frozenset(derived) == expected
        and len(derived) == len(expected)
        and derived == tuple(sorted(derived))
    )


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


def plan_repetition_is_identical(
    first: bytes,
    repeated: bytes,
    first_plan_id: str,
    repeated_plan_id: str,
) -> bool:
    """Judge repeat planning by canonical bytes and content-derived identity."""
    return first == repeated and first_plan_id == repeated_plan_id
