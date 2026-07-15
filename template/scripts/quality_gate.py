#!/usr/bin/env python3
"""Canonical local and CI quality gate."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import cast

LIKEC4_PROJECT = "docs/architecture/likec4"


@dataclass(frozen=True, slots=True, kw_only=True)
class Check:
    name: str
    command: tuple[str, ...]
    missing_tool_hint: str | None = None


def table(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a TOML table")
    return cast("dict[str, object]", value)


def likec4_version(root: Path) -> str:
    """Read the pinned LikeC4 CLI version from its single home in pyproject.toml."""
    pyproject = table(
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")), "pyproject.toml"
    )
    likec4 = table(table(pyproject["tool"], "tool")["likec4"], "tool.likec4")
    version = likec4["version"]
    if not isinstance(version, str):
        raise TypeError("tool.likec4.version must be a string")
    return version


def checks(root: Path) -> tuple[Check, ...]:
    return (
        Check(name="lockfile", command=("uv", "lock", "--check")),
        Check(name="format", command=("ruff", "format", "--check", ".")),
        Check(name="lint", command=("ruff", "check", ".")),
        Check(name="types", command=("basedpyright", "--project", "pyproject.toml")),
        Check(
            name="architecture AST", command=(sys.executable, "-m", "scripts.architecture_guard")
        ),
        Check(name="docs guard", command=(sys.executable, "-m", "scripts.docs_guard")),
        Check(name="import contracts", command=("lint-imports",)),
        Check(
            name="diagram sync",
            command=(sys.executable, "-m", "scripts.sync_architecture_diagrams", "--check"),
        ),
        Check(
            name="diagram views",
            command=("bunx", f"likec4@{likec4_version(root)}", "validate", LIKEC4_PROJECT),
            missing_tool_hint=(
                "'bunx' was not found on PATH. Install Bun (https://bun.sh); it is a "
                "toolchain prerequisite alongside uv and just."
            ),
        ),
        Check(name="tests", command=("pytest",)),
    )


def run(check: Check, root: Path) -> int:
    print(f"\n=== {check.name} ===", flush=True)
    try:
        completed = subprocess.run(check.command, cwd=root, check=False)
    except FileNotFoundError:
        hint = check.missing_tool_hint or f"'{check.command[0]}' was not found on PATH."
        print(hint, file=sys.stderr)
        return 127
    return completed.returncode


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for check in checks(root):
        exit_code = run(check, root)
        if exit_code != 0:
            print(f"\nFAILED: {check.name} (exit {exit_code})", file=sys.stderr)
            return exit_code
    print("\nAll quality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
