#!/usr/bin/env python3
"""Canonical local and CI quality gate."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True, slots=True, kw_only=True)
class Check:
    name: str
    command: tuple[str, ...]


CHECKS = (
    Check(name="lockfile", command=("uv", "lock", "--check")),
    Check(name="format", command=("ruff", "format", "--check", ".")),
    Check(name="lint", command=("ruff", "check", ".")),
    Check(name="types", command=("basedpyright",)),
    Check(name="architecture AST", command=(sys.executable, "-m", "scripts.architecture_guard")),
    Check(name="import contracts", command=("lint-imports",)),
    Check(name="tests", command=("pytest",)),
)


def run(check: Check, root: Path) -> int:
    print(f"\n=== {check.name} ===", flush=True)
    completed = subprocess.run(check.command, cwd=root, check=False)
    return completed.returncode


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for check in CHECKS:
        exit_code = run(check, root)
        if exit_code != 0:
            print(f"\nFAILED: {check.name} (exit {exit_code})", file=sys.stderr)
            return exit_code
    print("\nAll quality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
