#!/usr/bin/env python3
"""Run repository-specific architecture fitness functions.

The guard owns file loading: each module is read and parsed once, every rule
family checks the same text and tree, and the inline exception marker
(``ARCH-EXCEPTION: ADR-XXXX``, ledger-backed) is honored in one place for
exactly the codes that admit it.
"""

import ast
from pathlib import Path
import sys
from typing import TYPE_CHECKING

from scripts.architecture_policy import load_policy
from scripts.architecture_rules import Violation, check_source, python_files
from scripts.none_discipline import check_none_discipline

if TYPE_CHECKING:
    from scripts.architecture_policy import Policy

MARKER_SUPPRESSIBLE_CODES = frozenset({"ARCH016", "ARCH017", "ARCH018"})


def suppressed(item: Violation, lines: list[str], policy: Policy) -> bool:
    return (
        item.code in MARKER_SUPPRESSIBLE_CODES and policy.exception_marker in lines[item.line - 1]
    )


def check_file(path: Path, policy: Policy) -> list[Violation]:
    """Read and parse one module, then run every rule family on it."""
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as error:
        return [
            Violation(
                path=path,
                line=error.lineno or 1,
                code="ARCH000",
                message=f"Cannot parse module: {error.msg}",
            )
        ]
    violations = check_source(path, text, tree, policy)
    violations.extend(check_none_discipline(path, tree, policy))
    lines = text.splitlines()
    return [item for item in violations if not suppressed(item, lines, policy)]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    violations = [item for path in python_files(policy) for item in check_file(path, policy)]
    if violations:
        for item in violations:
            print(item.render(root))
        print(f"\n{len(violations)} architecture violation(s).", file=sys.stderr)
        return 1
    print("Architecture guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
