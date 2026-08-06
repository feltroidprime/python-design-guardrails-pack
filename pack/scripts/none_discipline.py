"""ARCH016, ARCH017, and ARCH018: keep None out of the domain core.

`None` is edge data. Raw external input can be incomplete, but the domain
core must not inherit that uncertainty. These checks cover what is
mechanically observable. The judgment calls (explicit state types, null
objects, sentinels) stay in review and in ADRs.

- `ARCH016` fires on a collection field that defaults to `None` instead of
  an empty collection. Fix: use `field(default_factory=...)`, so every
  caller iterates without a `None` check.
- `ARCH017` fires on an optional field inside the domain layer. Fix: parse
  raw data into a strict value at the adapter boundary, or model the state
  as its own type.
- `ARCH018` fires on a domain function that returns an optional. Fix: raise
  a domain error, or model the absent state explicitly, instead of
  returning `None`.

The guard applies the inline `ARCH-EXCEPTION: ADR-NNNN` marker centrally.
"""

import ast
from typing import TYPE_CHECKING

from scripts.architecture_rules import Violation, dotted_name, is_under, violation

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.architecture_policy import Policy

# Builtin and collections/collections.abc spellings only: the deprecated
# typing aliases (List, Dict, ...) are already rejected by Ruff (UP006).
COLLECTION_TYPE_NAMES = frozenset(
    {
        "Collection",
        "Counter",
        "Iterable",
        "Iterator",
        "Mapping",
        "MutableMapping",
        "MutableSequence",
        "MutableSet",
        "OrderedDict",
        "Sequence",
        "Set",
        "defaultdict",
        "deque",
        "dict",
        "frozenset",
        "list",
        "set",
        "tuple",
    }
)

OPTIONAL_TYPE_NAMES = frozenset({"Optional", "typing.Optional"})


def union_arms(node: ast.expr) -> list[ast.expr]:
    """Flatten a PEP 604 union into its arms. A non-union is a single arm."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return union_arms(node.left) + union_arms(node.right)
    return [node]


def is_none_arm(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def optional_arms(annotation: ast.expr) -> list[ast.expr]:
    """Return the non-None arms when the annotation admits None, else []."""
    arms = union_arms(annotation)
    if len(arms) > 1 and any(is_none_arm(arm) for arm in arms):
        return [arm for arm in arms if not is_none_arm(arm)]
    if not isinstance(annotation, ast.Subscript):
        return []
    if dotted_name(annotation.value) in OPTIONAL_TYPE_NAMES:
        return [annotation.slice]
    return []


def base_type_name(node: ast.expr) -> str:
    """Unsubscripted, unqualified type name: `collections.abc.Sequence[int]` -> `Sequence`."""
    target = node.value if isinstance(node, ast.Subscript) else node
    return dotted_name(target).rsplit(".", maxsplit=1)[-1]


def field_label(node: ast.AnnAssign) -> str:
    return dotted_name(node.target) or "<field>"


def check_collection_default(path: Path, node: ast.AnnAssign) -> list[Violation]:
    """ARCH016: a collection field defaults to an empty collection, never to None."""
    if not (isinstance(node.value, ast.Constant) and node.value.value is None):
        return []
    arms = optional_arms(node.annotation)
    if not any(base_type_name(arm) in COLLECTION_TYPE_NAMES for arm in arms):
        return []
    return [
        violation(
            path,
            node,
            "ARCH016",
            (
                f"Field '{field_label(node)}' defaults to None instead of an empty "
                "collection. Use field(default_factory=...) so callers iterate "
                "without a None check."
            ),
        )
    ]


def check_domain_field(path: Path, node: ast.AnnAssign) -> list[Violation]:
    """ARCH017: domain models never carry optional fields."""
    if not optional_arms(node.annotation):
        return []
    return [
        violation(
            path,
            node,
            "ARCH017",
            (
                f"Optional domain field '{field_label(node)}' forces None checks on "
                "every consumer. Parse raw data into a strict value at the adapter "
                "boundary, or model the state as its own type."
            ),
        )
    ]


def check_domain_return(
    path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[Violation]:
    """ARCH018: domain operations never signal absence or failure with None."""
    if node.returns is None or not optional_arms(node.returns):
        return []
    return [
        violation(
            path,
            node,
            "ARCH018",
            (
                f"Domain callable '{node.name}' returns an optional. Raise a domain "
                "error, or model the absent state explicitly."
            ),
        )
    ]


def class_fields(tree: ast.Module) -> list[ast.AnnAssign]:
    """Class-body annotated assignments anywhere in the module."""
    return [
        statement
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for statement in node.body
        if isinstance(statement, ast.AnnAssign)
    ]


def module_fields(tree: ast.Module) -> list[ast.AnnAssign]:
    """Module-level annotated assignments (function locals stay exempt)."""
    return [statement for statement in tree.body if isinstance(statement, ast.AnnAssign)]


def check_none_discipline(path: Path, tree: ast.Module, policy: Policy) -> list[Violation]:
    """Run every None-discipline check on one already-parsed module."""
    in_domain = is_under(path, policy.domain_root)
    fields = class_fields(tree)
    violations: list[Violation] = []
    for field in (*module_fields(tree), *fields):
        violations.extend(check_collection_default(path, field))
    if in_domain:
        for field in fields:
            violations.extend(check_domain_field(path, field))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                violations.extend(check_domain_return(path, node))
    return violations
