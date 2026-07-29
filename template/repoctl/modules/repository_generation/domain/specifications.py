"""Independent predicates for repository-generation domain values."""

import re

SCHEMA_VERSION = 1
CAPABILITY_NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
LIFECYCLE_STATUSES = frozenset({"draft", "active", "retired"})
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


def operation_kind_is_valid(value: str) -> bool:
    """Return whether ``value`` belongs to the closed plan-operation vocabulary."""
    return value in OPERATION_KINDS


def precondition_is_valid(value: str) -> bool:
    """Return whether a write expects absence or one exact prior digest."""
    return value == "absent" or digest_is_valid(value)
