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


def _call_violations(path: Path, node: ast.Call, policy: Policy) -> list[Violation]:
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
    return []


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
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            violations.extend(_framework_imports(path, node, policy))
        if isinstance(node, ast.Call):
            violations.extend(_call_violations(path, node, policy))
        if isinstance(node, ast.Raise):
            violations.extend(_raise_violations(path, node, policy))
    return violations
