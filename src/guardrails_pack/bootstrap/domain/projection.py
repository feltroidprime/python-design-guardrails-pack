"""The substitution rule of Terminal Projection: swap bytes, rename components.

Step 2 of the projection swaps the two identity tokens in every file, and it
renames every path component equal to a pack token. Two components carry a
pack token in this tree, so a projection makes two renames.

The substitution is blind rather than driven by a list of sites. A list fails in
silence, and a silent failure ships the pack name inside a user's product. `R7`
reads the whole built tree back and states the same rule as a check.
"""

from collections.abc import Sequence

from guardrails_pack.bootstrap.domain.identity import Identity

__all__ = ["BLOB_NAME", "found_tokens", "is_staged_blob", "rename_components", "swap_tokens"]

SEPARATOR = "/"
ENCODING = "utf-8"
# The archive that a release stages inside the package and deletes again. Step 1
# of the projection excludes it: an interrupted build leaves it in the tree, and
# a copy of it would ship the whole Root Pack inside a Terminal Project.
BLOB_NAME = "_pack.tar"
SOURCE_DIRECTORY = "src"
BLOB_DEPTH = 3


def is_staged_blob(relative: str) -> bool:
    """Whether one relative path is the staged projection blob of any package."""
    parts = relative.split(SEPARATOR)
    return len(parts) == BLOB_DEPTH and parts[0] == SOURCE_DIRECTORY and parts[-1] == BLOB_NAME


def rename_components(relative: str, pairs: Sequence[tuple[str, str]]) -> str:
    """Rename every component of one relative path that equals a pack token."""
    replacements = dict(pairs)
    return SEPARATOR.join(
        replacements.get(component, component) for component in relative.split(SEPARATOR)
    )


def swap_tokens(data: bytes, pairs: Sequence[tuple[str, str]]) -> bytes:
    """Swap both identity tokens in the bytes of one file."""
    swapped = data
    for old, new in pairs:
        swapped = swapped.replace(old.encode(ENCODING), new.encode(ENCODING))
    return swapped


def found_tokens(data: bytes, pack: Identity) -> tuple[str, ...]:
    """Every pack token that survives in the bytes of one built file (`R7`)."""
    return tuple(
        token for token in (pack.project_name, pack.package) if token.encode(ENCODING) in data
    )
