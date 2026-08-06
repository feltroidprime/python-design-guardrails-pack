"""ARCH021, ARCH022, and ARCH023: the one command-line seam of the package.

`_foundation/` is the pack-owned command seam. `_foundation/router.py` is
the only module that reaches an argument parser, and the only module that
ends the process. A capability never selects an exit code. It returns a
value or raises, and the router turns that into the exit code.

- `ARCH021` fires on a prompt call (`input`, `prompt`, `confirm`) inside
  `_foundation/`. Fix: delete the prompt. An unattended command path must
  never block on stdin.
- `ARCH022` fires on an uncontrolled process exit (`exit`, `quit`,
  `sys.exit`, `os._exit`) or on a raised `SystemExit`, outside
  `_foundation/router.py`. Fix: return a value or raise a domain exception
  instead, and let the router choose the exit code.
- `ARCH023` fires on an import of a CLI framework (`argparse`, `click`,
  `docopt`, `fire`, `typer`) outside `_foundation/router.py`. Fix: delete
  the import. A capability exposes its `api.py`, and only the router parses
  arguments.
"""

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

FOUNDATION_DIRECTORY = "_foundation"
ROUTER_MODULE = "router.py"


def foundation_root(policy: Policy) -> Path:
    """The pack-owned command seam of the package."""
    return policy.package_root / FOUNDATION_DIRECTORY


def router_module(policy: Policy) -> Path:
    """The one module that owns the argument parser and the process exit."""
    return foundation_root(policy) / ROUTER_MODULE


def _framework_imports(
    path: Path, node: ast.Import | ast.ImportFrom, policy: Policy
) -> list[Violation]:
    router = router_module(policy)
    violations: list[Violation] = []
    for root in sorted(import_roots(node) & CLI_FRAMEWORK_ROOTS):
        if path == router and root == "argparse":
            continue
        violations.append(
            violation(
                path,
                node,
                "ARCH023",
                f"CLI framework '{root}' is private to _foundation/router.py.",
            )
        )
    return violations


def _call_violations(path: Path, node: ast.Call, policy: Policy) -> list[Violation]:
    name = dotted_name(node.func)
    suffix = name.rsplit(".", maxsplit=1)[-1]
    if suffix in PROMPT_CALLS and is_under(path, foundation_root(policy)):
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
    if path == router_module(policy) or node.exc is None:
        return []
    raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    if dotted_name(raised) not in {"SystemExit", "builtins.SystemExit"}:
        return []
    return [
        violation(
            path,
            node,
            "ARCH022",
            "SystemExit is controlled only by _foundation/router.py.",
        )
    ]


def check_cli_discipline(path: Path, tree: ast.Module, policy: Policy) -> list[Violation]:
    """Check production source modules for forbidden automation drift."""
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
