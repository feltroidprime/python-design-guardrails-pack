"""Review-harvest checks."""

import ast
import io
import re
import tokenize
from typing import TYPE_CHECKING

from scripts.architecture_rules import Violation, dotted_name, violation
from scripts.path_discipline import annotated_args

if TYPE_CHECKING:
    from pathlib import Path

type Modules = tuple[tuple[Path, ast.Module], ...]

PRIMITIVES = ("float", "int", "str")
ENUMS = ("Enum", "Flag", "IntEnum", "IntFlag", "StrEnum")
MUTABLE_CALLS = ("builtins.dict", "builtins.list", "builtins.set", "dict", "list", "set")
PRIMITIVE_ALLOWLIST = ("JsonNumber", "JsonString")
MANUAL_VERBS = r"\b(?:bump|update|adjust) (?:this|it|these|both)\b"
MANUAL_TRIGGERS = r"\b(?:when|whenever|after|before|manually|by hand)\b"
REMINDER_PATTERNS = (
    re.compile(r"\bremember to\b", re.IGNORECASE),
    re.compile(r"\bdo(?: not|n't) forget\b", re.IGNORECASE),
    re.compile(r"\b(?:keep|keeps|keeping|kept)\b[^.;#]{0,32}\bin sync\b", re.IGNORECASE),
    re.compile(MANUAL_VERBS + r"[^.;#]{0,32}" + MANUAL_TRIGGERS, re.IGNORECASE),
    re.compile(r"\bmust (?:be |stay )?(?:bumped|updated|synced|adjusted)\b", re.IGNORECASE),
    re.compile(r"\bmanually\b[^.;#]{0,24}\b(?:bump|update|sync|copy)", re.IGNORECASE),
)


def _names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return tuple(item.id for item in targets if isinstance(item, ast.Name))


def _module_scope(tree: ast.Module) -> tuple[ast.stmt, ...]:
    result: list[ast.stmt] = []
    pending: list[ast.AST] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.stmt):
            result.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return tuple(result)


def _mutable_state(path: Path, tree: ast.Module) -> list[Violation]:
    """ARCH026: mutable module containers."""
    result: list[Violation] = []
    for node in _module_scope(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        value = node.value
        mutable = isinstance(value, (ast.Dict, ast.List, ast.Set)) or (
            isinstance(value, ast.Call) and dotted_name(value.func) in MUTABLE_CALLS
        )
        for name in _names(node):
            allowed_all = name == "__all__" and (
                isinstance(value, ast.List)
                or (
                    isinstance(value, ast.Call)
                    and dotted_name(value.func) in ("builtins.list", "list")
                )
            )
            if mutable and not allowed_all:
                result.append(
                    violation(
                        path,
                        node,
                        "ARCH026",
                        f"Module variable '{name}' owns mutable state; use an immutable value.",
                    )
                )
    return result


def _enum_signature(node: ast.ClassDef) -> tuple[str, ...] | None:
    bases = {dotted_name(base).rsplit(".", 1)[-1] for base in node.bases}
    if bases.isdisjoint(ENUMS):
        return None
    signature = tuple(
        ast.dump(item, include_attributes=False)
        for item in node.body
        if isinstance(item, (ast.Assign, ast.AnnAssign)) and item.value is not None
    )
    return signature or None


def _duplicate_enums(modules: Modules) -> list[Violation]:
    """ARCH027: exact same-named Enums only."""
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[Violation] = []
    for path, tree in modules:
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            signature = _enum_signature(node)
            if signature is None:
                continue
            key = (node.name, signature)
            if key in seen:
                result.append(
                    violation(
                        path,
                        node,
                        "ARCH027",
                        f"Model '{node.name}' is duplicated; keep one owner.",
                    )
                )
            seen.add(key)
    return result


def _boundary_names(tree: ast.Module) -> frozenset[str]:
    annotations: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            annotations.extend(value for _arg, value in annotated_args(node))
            if node.returns is not None:
                annotations.append(node.returns)
        elif isinstance(node, ast.ClassDef) and any(
            dotted_name(item.func if isinstance(item, ast.Call) else item).rsplit(".", 1)[-1]
            == "dataclass"
            for item in node.decorator_list
        ):
            annotations.extend(
                item.annotation for item in node.body if isinstance(item, ast.AnnAssign)
            )
    return frozenset(
        name.id
        for annotation in annotations
        for name in ast.walk(annotation)
        if isinstance(name, ast.Name)
    )


def _primitive_aliases(path: Path, tree: ast.Module) -> list[Violation]:
    """ARCH029: local CamelCase primitive aliases."""
    used = _boundary_names(tree)
    result: list[Violation] = []
    for node in tree.body:
        if isinstance(node, ast.TypeAlias):
            name, value = node.name.id, node.value
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name, value = node.targets[0].id, node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and dotted_name(node.annotation).rsplit(".", 1)[-1] == "TypeAlias"
            and node.value is not None
        ):
            name, value = node.target.id, node.value
        else:
            continue
        primitive = dotted_name(value)
        concept = name.isalnum() and name[:1].isupper() and not name.isupper()
        if primitive in PRIMITIVES and concept and name in used and name not in PRIMITIVE_ALLOWLIST:
            result.append(
                violation(
                    path,
                    node,
                    "ARCH029",
                    f"Domain type '{name}' is bare {primitive}; define a closed variant.",
                )
            )
    return result


def _reminder_comments(path: Path, text: str) -> list[Violation]:
    """ARCH031: comments that schedule manual upkeep."""
    result: list[Violation] = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.COMMENT:
            continue
        if any(pattern.search(token.string) for pattern in REMINDER_PATTERNS):
            result.append(
                Violation(
                    path=path,
                    line=token.start[0],
                    code="ARCH031",
                    message=(
                        "Comment schedules manual upkeep; derive the value or "
                        "enforce the invariant with a test or gate check."
                    ),
                )
            )
    return result


def check_review_discipline(path: Path, text: str, tree: ast.Module) -> list[Violation]:
    return [
        *_mutable_state(path, tree),
        *_primitive_aliases(path, tree),
        *_reminder_comments(path, text),
    ]


def check_repository_review_discipline(modules: Modules) -> list[Violation]:
    return _duplicate_enums(modules)
