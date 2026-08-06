"""The one ownership predicate of this tree.

**Pack-owned** is the `pack/` directory at the repository root, plus
`_`-prefixed names and `py.typed` inside `src/<pkg>/`. **User-owned** is
everything else. Two zones, one predicate, no path list.

A pack update replaces every pack-owned file whole. An edit inside `pack/`,
or inside a `_`-prefixed name under `src/<pkg>/`, is lost at the next
update. Keep a local change outside those paths, or it does not survive.

The predicate is total. It answers every repository-relative POSIX path and
raises nothing, so a caller classifies a path without a catalog and without
a declaration.
"""

import icontract

from scripts.ownership_specifications import pack_owned_is_exact

__all__ = ["pack_owned"]


def _pack_owned_is_exact(rel: str, pkg: str, *, result: bool) -> bool:
    return pack_owned_is_exact(rel, pkg, result=result)


@icontract.ensure(
    _pack_owned_is_exact,
    description="PROPERTY[PACK::PACK-OWNED]",
)
def pack_owned(rel: str, pkg: str) -> bool:
    """Answer whether one repository-relative path belongs to the pack."""
    parts = rel.split("/")
    if parts[0] == "pack":
        return True
    if parts[:2] == ["src", pkg] and len(parts) > 2:
        return parts[2].startswith("_") or parts[2] == "py.typed"
    return False
