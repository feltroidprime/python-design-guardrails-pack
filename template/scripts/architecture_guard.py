#!/usr/bin/env python3
"""Run repository-specific architecture fitness functions."""

from pathlib import Path
import sys

from scripts.architecture_policy import load_policy
from scripts.architecture_rules import check_module, python_files


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    violations = [item for path in python_files(policy) for item in check_module(path, policy)]
    if violations:
        for item in violations:
            print(item.render(root))
        print(f"\n{len(violations)} architecture violation(s).", file=sys.stderr)
        return 1
    print("Architecture guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
