"""Path-discipline fitness functions.

A filesystem location is a ``pathlib.Path`` from the moment it exists; a
``str`` path is wire data (argv, JSON payloads, database columns) that the
adapter parses at first touch, exactly as "None discipline" parses raw
optionals. Ruff's PTH rules already reject the ``os.path`` API at call sites;
these checks cover what a call-site linter cannot see — signatures and fields
whose names say "path" but whose types say ``str``. Once a boundary is typed
``Path``, basedpyright propagates the obligation to every caller, so the
guard only needs to police declarations. The judgment calls (what counts as
wire data, when a published API may accept ``os.PathLike``) stay in AGENTS.md
and ADRs. The guard applies the inline ``ARCH-EXCEPTION: ADR-XXXX`` marker
centrally.
"""

import ast
from typing import TYPE_CHECKING

from scripts.architecture_rules import Violation, dotted_name, violation
from scripts.none_discipline import class_fields, module_fields

if TYPE_CHECKING:
    from pathlib import Path

# Whole snake_case words that mark an identifier as naming a filesystem
# location. Token matching (never substring) keeps `profile` or `dirty` clean.
PATH_TOKENS = frozenset(
    {
        "dir",
        "directories",
        "directory",
        "dirname",
        "dirpath",
        "dirs",
        "filename",
        "filenames",
        "filepath",
        "filepaths",
        "folder",
        "folders",
        "path",
        "paths",
    }
)

# `file` names a path only as the last word: `config_file` is a path,
# `file_format` is not.
TRAILING_PATH_TOKENS = frozenset({"file", "files"})

# In a mapping named for its keys (`files: dict[Path, str]`), only the key
# position carries the path; the value is ordinary data (often file content).
MAPPING_TYPE_NAMES = frozenset(
    {"Counter", "Mapping", "MutableMapping", "OrderedDict", "defaultdict", "dict"}
)


def names_a_path(identifier: str) -> bool:
    tokens = identifier.lower().split("_")
    return tokens[-1] in TRAILING_PATH_TOKENS or not PATH_TOKENS.isdisjoint(tokens)


def subscript_base(node: ast.Subscript) -> str:
    return dotted_name(node.value).rsplit(".", maxsplit=1)[-1]


def admits_str(annotation: ast.expr) -> bool:
    """True when the annotation lets a str travel where the name promises a path.

    Covers the plain annotation, union arms (`str | Path` still forces every
    consumer to re-normalize), element types (`list[str]`), and mapping keys —
    but not mapping values or `Callable` signatures, which describe other data.
    """
    if isinstance(annotation, ast.Name):
        return annotation.id == "str"
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return admits_str(annotation.left) or admits_str(annotation.right)
    if not isinstance(annotation, ast.Subscript):
        return False
    base = subscript_base(annotation)
    if base == "Callable":
        return False
    slice_ = annotation.slice
    elements = list(slice_.elts) if isinstance(slice_, ast.Tuple) else [slice_]
    if base in MAPPING_TYPE_NAMES:
        return admits_str(elements[0])
    return any(admits_str(element) for element in elements)


def annotated_args(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[ast.arg, ast.expr]]:
    arguments = node.args
    return [
        (arg, arg.annotation)
        for arg in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
            arguments.vararg,
            arguments.kwarg,
        )
        if arg is not None and arg.annotation is not None
    ]


def check_signature(path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[Violation]:
    """ARCH019: a parameter or return that names a path is typed Path, never str."""
    violations = [
        violation(
            path,
            arg,
            "ARCH019",
            (
                f"Parameter '{arg.arg}' of '{node.name}' names a filesystem path but "
                "admits str; accept pathlib.Path and parse raw text where it enters "
                "(see 'Path discipline')."
            ),
        )
        for arg, annotation in annotated_args(node)
        if names_a_path(arg.arg) and admits_str(annotation)
    ]
    if node.returns is not None and names_a_path(node.name) and admits_str(node.returns):
        violations.append(
            violation(
                path,
                node,
                "ARCH019",
                (
                    f"Callable '{node.name}' names a path but returns str; return "
                    "pathlib.Path and serialize with str(path) only inside the final "
                    "external call."
                ),
            )
        )
    return violations


def check_field(path: Path, node: ast.AnnAssign) -> list[Violation]:
    """ARCH020: a field that names a path is typed Path, never str."""
    name = dotted_name(node.target)
    if not name or not names_a_path(name.rsplit(".", maxsplit=1)[-1]):
        return []
    if not admits_str(node.annotation):
        return []
    return [
        violation(
            path,
            node,
            "ARCH020",
            (
                f"Field '{name}' names a filesystem path but admits str; declare it "
                "as pathlib.Path and convert wire data at the adapter boundary."
            ),
        )
    ]


def check_path_discipline(path: Path, tree: ast.Module) -> list[Violation]:
    """Run every path-discipline check on one already-parsed module."""
    violations: list[Violation] = []
    for field in (*module_fields(tree), *class_fields(tree)):
        violations.extend(check_field(path, field))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(check_signature(path, node))
    return violations
