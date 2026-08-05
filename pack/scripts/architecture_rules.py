"""Repository-specific AST fitness functions.

The guard checks properties generic linters cannot express: domain purity,
immutable domain messages, dumping-ground modules, explicit exceptions, and
size ceilings. It deliberately does not pretend to prove subjective quality.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.architecture_policy import Policy

TYPE_IGNORE_TOKEN = "type:" + " ignore"
PYRIGHT_IGNORE_TOKEN = "pyright:" + " ignore"
NOQA_TOKEN = "no" + "qa"
DOMAIN_SCOPE = "Domain"


@dataclass(frozen=True, slots=True, kw_only=True)
class Violation:
    path: Path
    line: int
    code: str
    message: str

    def render(self, root: Path) -> str:
        return f"{self.path.relative_to(root)}:{self.line}: {self.code} {self.message}"


def is_under(path: Path, parent: Path) -> bool:
    try:
        _ = path.relative_to(parent)
    except ValueError:
        return False
    return True


def is_test_source(path: Path, policy: Policy) -> bool:
    """Both test trees: the user's `tests/` and the pack's own test roots."""
    return any(is_under(path, root) for root in policy.test_roots)


def dotted_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def import_roots(node: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name.split(".", maxsplit=1)[0] for alias in node.names}
    if node.module is None:
        return set()
    return {node.module.split(".", maxsplit=1)[0]}


def decorator_call(node: ast.expr, name: str) -> ast.Call | None:
    if isinstance(node, ast.Call) and dotted_name(node.func).endswith(name):
        return node
    return None


def truthy_keywords(call: ast.Call) -> set[str]:
    return {
        keyword.arg
        for keyword in call.keywords
        if keyword.arg is not None
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
    }


def node_length(node: ast.AST) -> int:
    end_line = getattr(node, "end_lineno", None)
    start_line = getattr(node, "lineno", None)
    if not isinstance(end_line, int) or not isinstance(start_line, int):
        return 0
    return end_line - start_line + 1


def violation(path: Path, node: ast.AST, code: str, message: str) -> Violation:
    line = getattr(node, "lineno", 1)
    return Violation(
        path=path, line=line if isinstance(line, int) else 1, code=code, message=message
    )


def check_suppressions(path: Path, text: str, policy: Policy) -> list[Violation]:
    violations: list[Violation] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if TYPE_IGNORE_TOKEN in line:
            violations.append(
                Violation(
                    path=path,
                    line=line_number,
                    code="ARCH008",
                    message="Use a narrow pyright suppression with an ADR-backed exception.",
                )
            )
        if PYRIGHT_IGNORE_TOKEN in line and policy.exception_marker not in line:
            violations.append(
                Violation(
                    path=path,
                    line=line_number,
                    code="ARCH009",
                    message=f"Pyright suppression requires '{policy.exception_marker}XXXX'.",
                )
            )
        if NOQA_TOKEN in line and policy.exception_marker not in line:
            violations.append(
                Violation(
                    path=path,
                    line=line_number,
                    code="ARCH010",
                    message=f"Ruff suppression requires '{policy.exception_marker}XXXX'.",
                )
            )
    return violations


def check_init_file(path: Path, text: str, policy: Policy) -> list[Violation]:
    """Every __init__.py must earn its existence.

    Test packages are namespace packages (PEP 420), so __init__.py is banned
    there outright. Elsewhere an __init__.py must state its package's public
    surface or ownership; an empty marker file is noise.
    """
    if path.name != "__init__.py":
        return []
    if is_test_source(path, policy):
        return [
            Violation(
                path=path,
                line=1,
                code="ARCH014",
                message="Test packages are namespace packages; delete this __init__.py.",
            )
        ]
    if not text.strip():
        return [
            Violation(
                path=path,
                line=1,
                code="ARCH015",
                message=(
                    "Empty __init__.py is forbidden; state the package surface "
                    "or ownership in a docstring."
                ),
            )
        ]
    return []


def check_module_shape(path: Path, line_count: int, policy: Policy) -> list[Violation]:
    violations: list[Violation] = []
    is_test = is_test_source(path, policy)
    maximum = policy.max_test_module_lines if is_test else policy.max_module_lines
    if path.stem in policy.forbidden_module_stems:
        violations.append(
            Violation(
                path=path,
                line=1,
                code="ARCH001",
                message="Generic module name is forbidden.",
            )
        )
    if line_count > maximum:
        violations.append(
            Violation(
                path=path,
                line=1,
                code="ARCH002",
                message=f"Module has {line_count} lines; maximum is {maximum}.",
            )
        )
    return violations


def check_function(
    path: Path,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    policy: Policy,
    *,
    in_domain: bool,
) -> list[Violation]:
    violations: list[Violation] = []
    length = node_length(node)
    if length > policy.max_function_lines:
        violations.append(
            violation(
                path,
                node,
                "ARCH003",
                (
                    f"Function '{node.name}' has {length} lines; "
                    f"maximum is {policy.max_function_lines}."
                ),
            )
        )
    if in_domain and isinstance(node, ast.AsyncFunctionDef):
        violations.append(violation(path, node, "ARCH004", "Domain logic must be synchronous."))
    return violations


def check_class(
    path: Path,
    node: ast.ClassDef,
    policy: Policy,
    *,
    immutable_domain_module: bool,
) -> list[Violation]:
    violations: list[Violation] = []
    length = node_length(node)
    if length > policy.max_class_lines:
        violations.append(
            violation(
                path,
                node,
                "ARCH005",
                f"Class '{node.name}' has {length} lines; maximum is {policy.max_class_lines}.",
            )
        )
    if not immutable_domain_module:
        return violations
    calls = [
        call
        for decorator in node.decorator_list
        if (call := decorator_call(decorator, "dataclass")) is not None
    ]
    if not calls:
        violations.append(
            violation(
                path,
                node,
                "ARCH006",
                "Classes in immutable modules must be dataclasses.",
            )
        )
    elif not {"frozen", "slots", "kw_only"}.issubset(truthy_keywords(calls[0])):
        violations.append(
            violation(
                path,
                node,
                "ARCH007",
                "Immutable dataclass requires frozen=True, slots=True, kw_only=True.",
            )
        )
    return violations


def check_import(
    path: Path,
    node: ast.Import | ast.ImportFrom,
    policy: Policy,
    *,
    ambient_effect_scope: str | None,
) -> list[Violation]:
    violations: list[Violation] = []
    if ambient_effect_scope is not None:
        forbidden_roots = import_roots(node) & policy.forbidden_import_roots
        violations.extend(
            violation(
                path,
                node,
                "ARCH011",
                (
                    f"{ambient_effect_scope} must not import '{root}'; "
                    "inject the capability through a port."
                ),
            )
            for root in sorted(forbidden_roots)
        )
    if (
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
    ):
        violations.append(
            violation(path, node, "ARCH013", "Use Python 3.14 native deferred annotations.")
        )
    return violations


def check_call(
    path: Path,
    node: ast.Call,
    policy: Policy,
    *,
    ambient_effect_scope: str | None,
) -> list[Violation]:
    if ambient_effect_scope is None:
        return []
    name = dotted_name(node.func)
    forbidden = any(
        name == suffix or name.endswith(f".{suffix}") for suffix in policy.forbidden_call_suffixes
    )
    if not forbidden:
        return []
    message = f"{ambient_effect_scope} call '{name}' is nondeterministic or performs I/O."
    return [
        violation(
            path,
            node,
            "ARCH012",
            message,
        )
    ]


def is_domain_source(path: Path, policy: Policy) -> bool:
    """Recognize the domain layer of one capability in the package."""
    return is_under(path, policy.package_root) and (
        policy.domain_root.name in path.relative_to(policy.package_root).parts[:-1]
    )


def ambient_effect_scope(path: Path, policy: Policy) -> str | None:
    """Name source layers whose decisions must remain free of ambient effects."""
    return DOMAIN_SCOPE if is_domain_source(path, policy) else None


def check_tree(path: Path, tree: ast.AST, policy: Policy) -> list[Violation]:
    violations: list[Violation] = []
    in_domain = is_domain_source(path, policy)
    effect_scope = ambient_effect_scope(path, policy)
    immutable = in_domain and path.stem in policy.immutable_module_stems
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(check_function(path, node, policy, in_domain=in_domain))
        if isinstance(node, ast.ClassDef):
            violations.extend(check_class(path, node, policy, immutable_domain_module=immutable))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            violations.extend(check_import(path, node, policy, ambient_effect_scope=effect_scope))
        if isinstance(node, ast.Call):
            violations.extend(check_call(path, node, policy, ambient_effect_scope=effect_scope))
    return violations


def check_source(path: Path, text: str, tree: ast.Module, policy: Policy) -> list[Violation]:
    """Run every general fitness function on one already-parsed module.

    The guard owns reading and parsing (and reports ARCH000 for unparsable
    files), so every rule family checks the same text and tree.
    """
    violations = check_suppressions(path, text, policy)
    violations.extend(check_init_file(path, text, policy))
    violations.extend(check_module_shape(path, len(text.splitlines()), policy))
    violations.extend(check_tree(path, tree, policy))
    return violations


def python_files(policy: Policy) -> list[Path]:
    """Every Python file the guard owns: the package, the pack, and the tests."""
    roots = [policy.source_root, policy.root / "tests", policy.pack_root]
    return sorted(
        path for root in roots if root.is_dir() for path in root.rglob("*.py") if path.is_file()
    )
