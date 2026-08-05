"""ARCH030 for direct local/imported bases; ambiguous or dynamic bases skip."""

import ast
from typing import TYPE_CHECKING

from scripts.architecture_rules import Violation, dotted_name, violation

if TYPE_CHECKING:
    from pathlib import Path

type Modules = tuple[tuple[Path, ast.Module], ...]
type Method = ast.AsyncFunctionDef | ast.FunctionDef


def _marked(method: Method) -> bool:
    return any(
        dotted_name(item.func if isinstance(item, ast.Call) else item).rsplit(".", 1)[-1]
        == "override"
        for item in method.decorator_list
    )


def _imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
    return {
        item.asname or item.name: (item.name, statement.module)
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom)
        and statement.level == 0
        and statement.module is not None
        for item in statement.names
    }


def check_override_discipline(modules: Modules) -> list[Violation]:
    classes = tuple(
        (path, tree, node)
        for path, tree in modules
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    )
    result: list[Violation] = []
    for path, tree, node in classes:
        imports = _imports(tree)
        inherited: set[str] = set()
        for expression in node.bases:
            target = expression.value if isinstance(expression, ast.Subscript) else expression
            if isinstance(target, ast.Name):
                name, module = imports.get(target.id, (target.id, None))
            elif "." in (qualified := dotted_name(target)):
                module, _, name = qualified.rpartition(".")
            else:
                continue
            module_path = "" if module is None else module.replace(".", "/")
            matches = tuple(
                candidate
                for owner_path, _tree, candidate in classes
                if candidate.name == name
                and (
                    owner_path == path
                    if module is None
                    else owner_path.as_posix().endswith(
                        (f"/{module_path}.py", f"/{module_path}/__init__.py")
                    )
                )
            )
            if len(matches) == 1:
                inherited.update(
                    method.name
                    for method in matches[0].body
                    if isinstance(method, (ast.AsyncFunctionDef, ast.FunctionDef))
                )
        result.extend(
            violation(
                path,
                method,
                "ARCH030",
                f"Method '{node.name}.{method.name}' overrides a base; add @override.",
            )
            for method in node.body
            if isinstance(method, (ast.AsyncFunctionDef, ast.FunctionDef))
            and method.name in inherited
            and not _marked(method)
        )
    return result
