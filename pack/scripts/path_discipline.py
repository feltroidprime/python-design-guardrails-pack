"""Path declaration and use checks (ARCH019/020/028)."""

import ast
from typing import TYPE_CHECKING

from scripts.architecture_rules import Violation, dotted_name, violation
from scripts.none_discipline import class_fields, module_fields

if TYPE_CHECKING:
    from pathlib import Path

# Whole-word matching keeps `profile` and `dirty` clean.
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

# `file` is path-like only as the final word.
TRAILING_PATH_TOKENS = frozenset({"file", "files"})

# Only a mapping's key position carries a path.
MAPPING_TYPE_NAMES = frozenset(
    {"Counter", "Mapping", "MutableMapping", "OrderedDict", "defaultdict", "dict"}
)
PATH_CONSTRUCTORS = frozenset(
    {"Path", "PosixPath", "PurePath", "PurePosixPath", "PureWindowsPath", "WindowsPath"}
)
PATH_FUNCTIONS = frozenset({"builtins.open", "open", "os.fspath"})
PATH_USAGE_METHODS = frozenset({"read_text", "write_text"})


def names_a_path(identifier: str) -> bool:
    tokens = identifier.lower().split("_")
    return tokens[-1] in TRAILING_PATH_TOKENS or not PATH_TOKENS.isdisjoint(tokens)


def subscript_base(node: ast.Subscript) -> str:
    return dotted_name(node.value).rsplit(".", maxsplit=1)[-1]


def admits_str(annotation: ast.expr) -> bool:
    """Whether a path declaration admits str, including unions/containers."""
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


def _path_operands(node: ast.AST) -> tuple[ast.expr, ...]:
    if not isinstance(node, ast.Call):
        return ()
    called = dotted_name(node.func)
    if called.rsplit(".", 1)[-1] in PATH_CONSTRUCTORS:
        return tuple(node.args)
    if called in PATH_FUNCTIONS:
        if node.args:
            return (node.args[0],)
        return tuple(item.value for item in node.keywords if item.arg in {"file", "path"})
    if isinstance(node.func, ast.Attribute) and node.func.attr in PATH_USAGE_METHODS:
        return (node.func.value,)
    return ()


def _uses_as_path(statements: list[ast.stmt], target: str) -> bool:
    """Whether a declaration reaches a path API in this lexical scope."""
    pending: list[ast.AST] = list(reversed(statements))
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Lambda)):
            continue
        if any(
            dotted_name(part) == target
            for operand in _path_operands(node)
            for part in ast.walk(operand)
            if isinstance(part, ast.expr)
        ):
            return True
        pending.extend(reversed(list(ast.iter_child_nodes(node))))
    return False


def _use_violation(path: Path, node: ast.AST, kind: str, name: str) -> Violation:
    return violation(
        path,
        node,
        "ARCH028",
        f"{kind} '{name}' is str used as a filesystem path; declare pathlib.Path.",
    )


def _check_untokenized_parameters(
    path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[Violation]:
    return [
        _use_violation(path, arg, "Parameter", arg.arg)
        for arg, annotation in annotated_args(node)
        if not names_a_path(arg.arg)
        and admits_str(annotation)
        and _uses_as_path(node.body, arg.arg)
    ]


def _check_untokenized_class_fields(path: Path, node: ast.ClassDef) -> list[Violation]:
    methods = tuple(
        item for item in node.body if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef))
    )
    fields = tuple(
        (item, item.target.id)
        for item in node.body
        if isinstance(item, ast.AnnAssign)
        and isinstance(item.target, ast.Name)
        and not names_a_path(item.target.id)
        and admits_str(item.annotation)
    )
    return [
        _use_violation(path, field, "Field", field_name)
        for field, field_name in fields
        if any(_uses_as_path(method.body, f"self.{field_name}") for method in methods)
    ]


def check_path_discipline(path: Path, tree: ast.Module) -> list[Violation]:
    """Run every path-discipline check on one already-parsed module."""
    violations: list[Violation] = []
    for field in (*module_fields(tree), *class_fields(tree)):
        violations.extend(check_field(path, field))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(check_signature(path, node))
            violations.extend(_check_untokenized_parameters(path, node))
        if isinstance(node, ast.ClassDef):
            violations.extend(_check_untokenized_class_fields(path, node))
    return violations
