"""Static guardrails for the agent-native command-line boundary."""

import ast
from typing import TYPE_CHECKING

from scripts.architecture_rules import (
    Violation,
    dotted_name,
    import_roots,
    is_under,
    violation,
)

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.architecture_policy import Policy

CLI_FRAMEWORK_ROOTS = frozenset({"argparse", "click", "docopt", "fire", "typer"})
PROMPT_CALLS = frozenset({"input", "prompt", "confirm"})
UNCONTROLLED_EXITS = frozenset({"exit", "quit", "sys.exit", "os._exit"})


def _framework_imports(
    path: Path, node: ast.Import | ast.ImportFrom, policy: Policy
) -> list[Violation]:
    cli_path = policy.package_root / "adapters" / "inbound" / "cli.py"
    violations: list[Violation] = []
    for root in sorted(import_roots(node) & CLI_FRAMEWORK_ROOTS):
        if path == cli_path and root == "argparse":
            continue
        violations.append(
            violation(
                path,
                node,
                "ARCH023",
                f"CLI framework '{root}' is private to adapters/inbound/cli.py.",
            )
        )
    return violations


def _call_violations(
    path: Path,
    node: ast.Call,
    policy: Policy,
    catalog_iterators: frozenset[str],
    command_spec_names: frozenset[str],
) -> list[Violation]:
    name = dotted_name(node.func)
    suffix = name.rsplit(".", maxsplit=1)[-1]
    automation_root = policy.package_root / "adapters" / "inbound"
    if suffix in PROMPT_CALLS and is_under(path, automation_root):
        return [
            violation(
                path,
                node,
                "ARCH021",
                f"Prompt call '{name}' is forbidden in unattended command paths.",
            )
        ]
    if name in UNCONTROLLED_EXITS:
        return [
            violation(
                path,
                node,
                "ARCH022",
                f"Process exit '{name}' bypasses the controlled CLI exit contract.",
            )
        ]
    return _registration_violations(path, node, policy, catalog_iterators, command_spec_names)


def _registration_violations(
    path: Path,
    node: ast.Call,
    policy: Policy,
    catalog_iterators: frozenset[str],
    command_spec_names: frozenset[str],
) -> list[Violation]:
    name = dotted_name(node.func)
    cli_path = policy.package_root / "adapters" / "inbound" / "cli.py"
    catalog_path = policy.package_root / "adapters" / "inbound" / "cli_catalog.py"
    lookup_argument: ast.expr | None = None
    attribute_arguments = node.args[1:]
    if name in {"getattr", "builtins.getattr"} and attribute_arguments:
        lookup_argument = attribute_arguments[0]
    elif name.endswith(".__getattribute__") and node.args:
        lookup_argument = node.args[0]
    if isinstance(lookup_argument, ast.Constant) and lookup_argument.value == "add_parser":
        return [
            violation(
                path,
                node,
                "ARCH024",
                "Dynamic attribute lookup cannot be used to register command parsers.",
            )
        ]
    if name.endswith(".add_subparsers") and path != cli_path:
        return [
            violation(
                path,
                node,
                "ARCH024",
                "Command parsers must be built from COMMAND_CATALOG.",
            )
        ]
    if name.endswith(".add_parser"):
        allowed_identities = {f"{iterator}.name.value" for iterator in catalog_iterators}
        catalog_identity = bool(node.args) and dotted_name(node.args[0]) in allowed_identities
        has_hidden_keywords = any(keyword.arg in {None, "aliases"} for keyword in node.keywords)
        if path != cli_path or not catalog_identity or has_hidden_keywords:
            return [
                violation(
                    path,
                    node,
                    "ARCH024",
                    "Command names and aliases must come directly from COMMAND_CATALOG.",
                )
            ]
    if name in command_spec_names or name.endswith(".CommandSpec"):
        if path != catalog_path:
            return [
                violation(
                    path,
                    node,
                    "ARCH024",
                    "CommandSpec instances belong only in adapters/inbound/cli_catalog.py.",
                )
            ]
        return _input_policy_violations(path, node)
    return []


def _input_policy_violations(path: Path, node: ast.Call) -> list[Violation]:
    policy_value = next(
        (keyword.value for keyword in node.keywords if keyword.arg == "input_policy"), None
    )
    primary_value: ast.expr | None = None
    if isinstance(policy_value, ast.Call) and dotted_name(policy_value.func).endswith(
        "InputPolicy"
    ):
        primary_value = next(
            (keyword.value for keyword in policy_value.keywords if keyword.arg == "primary"),
            None,
        )
    if primary_value is not None and dotted_name(primary_value) == "InputMode.ARGUMENTS":
        return []
    return [
        violation(
            path,
            node,
            "ARCH025",
            "Catalog commands require explicit ordinary arguments as primary input.",
        )
    ]


def _registration_reference_violations(
    path: Path, node: ast.Attribute, parent: ast.AST | None
) -> list[Violation]:
    if node.attr != "add_parser":
        return []
    if isinstance(parent, ast.Call) and parent.func is node:
        return []
    return [
        violation(
            path,
            node,
            "ARCH024",
            "Command parser registration cannot be aliased or passed indirectly.",
        )
    ]


def _catalog_iterators(tree: ast.Module) -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        if dotted_name(node.iter) != "COMMAND_CATALOG" or not isinstance(node.target, ast.Name):
            continue
        names.add(node.target.id)
    return frozenset(names)


def _command_spec_names(tree: ast.Module) -> frozenset[str]:
    names = {"CommandSpec"}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        for imported in node.names:
            if imported.name == "CommandSpec":
                names.add(imported.asname or imported.name)
    assignments = _constructor_assignments(tree)
    changed = True
    while changed:
        changed = False
        for target, source in assignments:
            if source not in names and not source.endswith(".CommandSpec"):
                continue
            if target not in names:
                names.add(target)
                changed = True
    return frozenset(names)


def _constructor_assignments(tree: ast.Module) -> tuple[tuple[str, str], ...]:
    bindings: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            source = dotted_name(node.value)
            bindings.extend(
                (target.id, source) for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                bindings.append((node.target.id, dotted_name(node.value)))
    return tuple(bindings)


def _raise_violations(path: Path, node: ast.Raise, policy: Policy) -> list[Violation]:
    if path == policy.package_root / "__main__.py" or node.exc is None:
        return []
    raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    if dotted_name(raised) not in {"SystemExit", "builtins.SystemExit"}:
        return []
    return [
        violation(
            path,
            node,
            "ARCH022",
            "SystemExit is controlled only by the package module entrypoint.",
        )
    ]


def check_cli_discipline(path: Path, tree: ast.Module, policy: Policy) -> list[Violation]:
    """Reject automation drift in production source modules."""
    if not is_under(path, policy.source_root):
        return []
    violations: list[Violation] = []
    catalog_iterators = _catalog_iterators(tree)
    command_spec_names = _command_spec_names(tree)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            violations.extend(_framework_imports(path, node, policy))
        if isinstance(node, ast.Call):
            violations.extend(
                _call_violations(path, node, policy, catalog_iterators, command_spec_names)
            )
        if isinstance(node, ast.Attribute):
            violations.extend(_registration_reference_violations(path, node, parents.get(node)))
        if isinstance(node, ast.Raise):
            violations.extend(_raise_violations(path, node, policy))
    return violations
