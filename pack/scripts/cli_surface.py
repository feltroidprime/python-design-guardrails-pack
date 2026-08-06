"""Static rules over every `<cap>/api.py`, composed or not.

The router derives one command group from each capability and one subcommand
from each public function of its `api.py`. It reads the signature and the
docstring, and nothing else. An api surface the router cannot render must
therefore fail at the gate, not at run time.

| Rule | The api surface must not hold |
|---|---|
| `CLI001` | a reserved parameter name |
| `CLI002` | a missing docstring on the module or on a public function |
| `CLI003` | an annotation outside the closed stdlib set |
| `CLI004` | a `bool` parameter without a `False` default |

`CLI003` reads two different sets. A parameter takes the narrower,
`RENDERABLE_PARAMETER_NAMES`, because the router turns it into one
command-line value: `None`, `Path`, `bool`, `float`, `int`, or `str`. A
return takes the wider `RENDERABLE_RETURN_NAMES`, because the router turns
it into one JSON document or one page of documents: every parameter name,
plus `Iterable`, `Iterator`, `Mapping`, `Sequence`, `dict`, `list`, `object`,
and `tuple`. The `CLI003` message names the accepted set for the position it
fires on. Fix a parameter with the parameter set. Fix a return with the
return set.

The rules read the filesystem layout only, so an uncomposed capability is
checked exactly like a composed one.
"""

import ast
from typing import TYPE_CHECKING

from scripts.architecture_rules import Violation, violation

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.architecture_policy import Policy

type Function = ast.AsyncFunctionDef | ast.FunctionDef

API_MODULE = "api.py"
PRIVATE_PREFIXES = (".", "_")

# The router turns each of these names into a global option of every command,
# so a capability cannot claim one for itself.
RESERVED_PARAMETER_NAMES = frozenset({"continuation", "debug", "format", "limit"})

# The closed set of annotation names the router can render. A parameter takes
# the scalar set, because it becomes one command-line value. A return takes the
# wider set, because it becomes one JSON document or one page of documents.
RENDERABLE_PARAMETER_NAMES = frozenset({"None", "Path", "bool", "float", "int", "str"})
RENDERABLE_RETURN_NAMES = RENDERABLE_PARAMETER_NAMES | frozenset(
    {"Iterable", "Iterator", "Mapping", "Sequence", "dict", "list", "object", "tuple"}
)


def is_capability_api(path: Path, policy: Policy) -> bool:
    """True for `<cap>/api.py`, where `<cap>` is a capability of this package."""
    if path.name != API_MODULE:
        return False
    capability = path.parent
    return capability.parent == policy.package_root and not capability.name.startswith(
        PRIVATE_PREFIXES
    )


def public_functions(tree: ast.Module) -> tuple[Function, ...]:
    """Every public function of the module, in source order."""
    return tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and not node.name.startswith("_")
    )


def parameters(node: Function) -> tuple[ast.arg, ...]:
    """Every parameter of one function, in declaration order."""
    arguments = node.args
    star = [item for item in (arguments.vararg, arguments.kwarg) if item is not None]
    return (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, *star)


def defaults(node: Function) -> dict[str, ast.expr | None]:
    """The default of each parameter, or `None` when the parameter has none."""
    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    missing: list[ast.expr | None] = [None] * (len(positional) - len(arguments.defaults))
    result: dict[str, ast.expr | None] = dict(
        zip(
            [item.arg for item in positional],
            [*missing, *arguments.defaults],
            strict=True,
        )
    )
    result.update(
        zip(
            [item.arg for item in arguments.kwonlyargs],
            arguments.kw_defaults,
            strict=True,
        )
    )
    return result


def annotation_names(annotation: ast.expr) -> tuple[str, ...]:
    """Every name one annotation mentions, with a dotted path reduced to its tail."""
    names: list[str] = []
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.Constant) and node.value is None:
            names.append("None")
    return tuple(names)


def _reserved_names(path: Path, node: Function) -> list[Violation]:
    """CLI001: a reserved parameter name."""
    return [
        violation(
            path,
            parameter,
            "CLI001",
            f"Parameter '{parameter.arg}' of '{node.name}' is a reserved router option.",
        )
        for parameter in parameters(node)
        if parameter.arg in RESERVED_PARAMETER_NAMES
    ]


def _missing_docstrings(path: Path, tree: ast.Module) -> list[Violation]:
    """CLI002: a missing docstring on the api module or on a public function."""
    violations: list[Violation] = []
    if ast.get_docstring(tree) is None:
        violations.append(
            Violation(
                path=path,
                line=1,
                code="CLI002",
                message="The api module states no docstring. The router shows it as group help.",
            )
        )
    violations.extend(
        violation(
            path,
            node,
            "CLI002",
            f"Public function '{node.name}' states no docstring. The router shows it as help.",
        )
        for node in public_functions(tree)
        if ast.get_docstring(node) is None
    )
    return violations


def _parameter_annotations(path: Path, node: Function) -> list[Violation]:
    violations: list[Violation] = []
    for parameter in parameters(node):
        if parameter.annotation is None:
            violations.append(
                violation(
                    path,
                    parameter,
                    "CLI003",
                    f"Parameter '{parameter.arg}' of '{node.name}' states no annotation.",
                )
            )
            continue
        rejected = sorted(set(annotation_names(parameter.annotation)) - RENDERABLE_PARAMETER_NAMES)
        if rejected:
            accepted = ", ".join(sorted(RENDERABLE_PARAMETER_NAMES))
            detail = (
                f"uses {', '.join(rejected)}, which the router cannot render. "
                f"A parameter must use one of: {accepted}"
            )
            violations.append(
                violation(
                    path,
                    parameter,
                    "CLI003",
                    f"Parameter '{parameter.arg}' of '{node.name}' {detail}.",
                )
            )
    return violations


def _unrenderable_annotations(path: Path, node: Function) -> list[Violation]:
    """CLI003: an annotation outside the closed stdlib set the router can render."""
    violations = _parameter_annotations(path, node)
    if node.returns is None:
        violations.append(
            violation(
                path,
                node,
                "CLI003",
                f"Function '{node.name}' states no return annotation.",
            )
        )
        return violations
    rejected = sorted(set(annotation_names(node.returns)) - RENDERABLE_RETURN_NAMES)
    if rejected:
        accepted = ", ".join(sorted(RENDERABLE_RETURN_NAMES))
        detail = (
            f"uses {', '.join(rejected)}, which the router cannot render. "
            f"A return must use one of: {accepted}"
        )
        violations.append(violation(path, node, "CLI003", f"The return of '{node.name}' {detail}."))
    return violations


def _boolean_defaults(path: Path, node: Function) -> list[Violation]:
    """CLI004: a `bool` parameter without a `False` default."""
    supplied = defaults(node)
    violations: list[Violation] = []
    for parameter in parameters(node):
        if parameter.annotation is None or annotation_names(parameter.annotation) != ("bool",):
            continue
        default = supplied.get(parameter.arg)
        if isinstance(default, ast.Constant) and default.value is False:
            continue
        violations.append(
            violation(
                path,
                parameter,
                "CLI004",
                f"Boolean parameter '{parameter.arg}' of '{node.name}' must default to False.",
            )
        )
    return violations


def check_capability_api(path: Path, tree: ast.Module, policy: Policy) -> list[Violation]:
    """Check an `api.py` surface for whatever the router cannot turn into commands."""
    if not is_capability_api(path, policy):
        return []
    violations = _missing_docstrings(path, tree)
    for node in public_functions(tree):
        violations.extend(_reserved_names(path, node))
        violations.extend(_unrenderable_annotations(path, node))
        violations.extend(_boolean_defaults(path, node))
    return violations
