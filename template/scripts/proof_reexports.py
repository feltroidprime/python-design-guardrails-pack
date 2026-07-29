"""Resolve stable public-facade calls to their defining proof symbols."""

import ast

from scripts.proof_model import DiscoveryError
from scripts.proof_sources import (
    SourceRoots,
    find_qualified_node,
    module_file,
)


def _imported_target(tree: ast.Module, qualname: str) -> str | None:
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 0:
            continue
        if node.module is None:
            continue
        for alias in node.names:
            if (alias.asname or alias.name) == qualname:
                return f"{node.module}:{alias.name}"
    return None


def _reexported_target(
    source_roots: SourceRoots,
    target: str,
    seen: frozenset[str],
) -> str:
    if target in seen:
        return target
    module, separator, qualname = target.partition(":")
    if not separator or "." in qualname:
        return target
    try:
        path = module_file(module, source_roots)
    except DiscoveryError:
        return target
    if path is None:
        return target
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if find_qualified_node(tree, qualname) is not None:
        return target
    imported = _imported_target(tree, qualname)
    if imported is None:
        return target
    return _reexported_target(source_roots, imported, seen | {target})


def resolve_reexported_target(source_roots: SourceRoots, target: str) -> str:
    """Resolve a called public-facade symbol to its defining proof symbol."""
    return _reexported_target(source_roots, target, frozenset())
