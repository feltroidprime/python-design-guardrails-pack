"""The ownership predicate, stated inside the capability that writes files.

**Pack-owned** is the `pack/` directory at the repository root, plus
`_`-prefixed names and `py.typed` inside `src/<pkg>/`. **User-owned** is
everything else. A Pack Update evaluates this predicate once per path, over
the whole write plan, before it touches any file. It never compares a path
against the manifest's path list. A file that the new version dropped is
absent from that list, and the update must still delete it.

`pack/scripts/ownership.py` states the same rule for the gate. The capability
contract forbids an import of pack code, so the rule stands twice, in two
zones, in two shapes. Two independent statements of one rule catch a defect in
either one.

The predicate is total. It answers every repository-relative POSIX path and
raises nothing.
"""

__all__ = ["SCANNED_SUFFIXES", "is_scanned", "pack_owned"]

SEPARATOR = "/"
PACK_DIRECTORY = "pack"
SOURCE_DIRECTORY = "src"
PRIVATE_PREFIX = "_"
TYPED_MARKER = "py.typed"

# Runtime output that lives inside the two pack-owned zones and belongs to no
# release: bytecode caches, tool caches, and the forced-update backups. The
# manifest records none of them, so a drift scan reads none of them either.
# Both zones use one list, so a cache directory can never enter a manifest and
# refuse every later update.
SCANNED_NAMES = frozenset(
    {
        ".basedpyright",
        ".drift",
        ".hypothesis",
        ".import_linter_cache",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
    }
)
SCANNED_SUFFIXES = (".pyc", ".pyo")
# The staged projection payload is one archive under `src/`. It belongs to no
# release and an interrupted build can leave it behind. `pack/scripts/
# manifest_guard.py` states the same rule for the gate. Both name the shape and
# never the file name, so a Terminal Project carries the rule unchanged.
SCANNED_SOURCE_SUFFIX = ".tar"


def pack_owned(rel: str, pkg: str) -> bool:
    """Answer whether one repository-relative path belongs to the pack."""
    parts = rel.split(SEPARATOR)
    if parts[0] == PACK_DIRECTORY:
        return True
    if parts[:2] == [SOURCE_DIRECTORY, pkg] and len(parts) > 2:
        return parts[2].startswith(PRIVATE_PREFIX) or parts[2] == TYPED_MARKER
    return False


def is_scanned(rel: str) -> bool:
    """Answer whether one repository-relative path is release content."""
    parts = rel.split(SEPARATOR)
    if any(part in SCANNED_NAMES for part in parts):
        return False
    if parts[0] == SOURCE_DIRECTORY and parts[-1].endswith(SCANNED_SOURCE_SUFFIX):
        return False
    return not parts[-1].endswith(SCANNED_SUFFIXES)
