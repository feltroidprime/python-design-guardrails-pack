"""Independent predicate for the pack-owned surface.

This module states the ownership rule a second time, in a different shape.
The implementation splits a path into segments. This oracle matches text
prefixes. Two independent statements of one rule catch a defect in either
one.
"""


def pack_owned_is_exact(rel: str, pkg: str, *, result: bool) -> bool:
    """Judge one pack-owned answer against an independently written rule."""
    if rel == "pack" or rel.startswith("pack/"):
        return result is True
    prefix = f"src/{pkg}/"
    if rel.startswith(prefix):
        name = rel.removeprefix(prefix).partition("/")[0]
        return result is (name.startswith("_") or name == "py.typed")
    return result is False
