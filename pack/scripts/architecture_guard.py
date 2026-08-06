#!/usr/bin/env python3
"""Run every architecture guard over one shared parse per module.

The `ARCH-EXCEPTION: ADR-NNNN` marker suppresses only `ARCH016` through
`ARCH030`. For `ARCH000` through `ARCH015` the marker does nothing, because
those codes are structural. To clear one of them, change the code, or change
`pack/architecture.toml` with a written rationale (see the change protocol of
AGENTS.md).

The marker also does nothing for `CLI001` through `CLI004`, for every `DOC`
code, and for every `PROOF` code. The marker text only ever matches the
literal codes `ARCH016` through `ARCH030`.

| Code range | Owning module | Marker-suppressible |
|---|---|---|
| `ARCH000` | this module | no |
| `ARCH001`-`ARCH015` | `architecture_rules.py` | no |
| `ARCH016`-`ARCH018` | `none_discipline.py` | yes |
| `ARCH019`, `ARCH020`, `ARCH028` | `path_discipline.py` | yes |
| `ARCH021`-`ARCH023` | `cli_discipline.py` | yes |
| `ARCH026`, `ARCH027`, `ARCH029` | `review_discipline.py` | yes |
| `ARCH030` | `override_discipline.py` | yes |
| `CLI001`-`CLI004` | `cli_surface.py` | no, not an ARCH code |
"""

import ast
from pathlib import Path
import sys
from typing import TYPE_CHECKING

from scripts.architecture_policy import load_policy
from scripts.architecture_rules import Violation, check_source, python_files
from scripts.cli_discipline import check_cli_discipline
from scripts.cli_surface import check_capability_api
from scripts.none_discipline import check_none_discipline
from scripts.override_discipline import check_override_discipline
from scripts.path_discipline import check_path_discipline
from scripts.review_discipline import (
    check_repository_review_discipline,
    check_review_discipline,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from scripts.architecture_policy import Policy

type ParsedModule = tuple[Path, str, ast.Module]

MARKER_SUPPRESSIBLE_CODES = frozenset(f"ARCH{number:03}" for number in range(16, 31))


def suppressed(item: Violation, lines: list[str], policy: Policy) -> bool:
    return (
        item.code in MARKER_SUPPRESSIBLE_CODES and policy.exception_marker in lines[item.line - 1]
    )


def check_files(paths: Iterable[Path], policy: Policy) -> list[Violation]:
    """Read each module once and run both file-local and repository-wide rules."""
    parsed: list[ParsedModule] = []
    violations: list[Violation] = []
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as error:
            violations.append(
                Violation(
                    path=path,
                    line=error.lineno or 1,
                    code="ARCH000",
                    message=f"Cannot parse module: {error.msg}",
                )
            )
            continue
        parsed.append((path, text, tree))
        violations.extend(check_source(path, text, tree, policy))
        violations.extend(check_none_discipline(path, tree, policy))
        violations.extend(check_path_discipline(path, tree))
        violations.extend(check_cli_discipline(path, tree, policy))
        violations.extend(check_capability_api(path, tree, policy))
        violations.extend(check_review_discipline(path, tree))
    modules = tuple((path, tree) for path, _text, tree in parsed)
    violations.extend(check_repository_review_discipline(modules))
    violations.extend(check_override_discipline(modules))
    lines_by_path = {path: text.splitlines() for path, text, _tree in parsed}
    unsuppressed = [
        item
        for item in violations
        if item.path not in lines_by_path or not suppressed(item, lines_by_path[item.path], policy)
    ]
    return sorted(unsuppressed, key=lambda item: (str(item.path), item.line, item.code))


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    policy = load_policy(root)
    violations = check_files(python_files(policy), policy)
    if violations:
        for item in violations:
            print(item.render(root))
        print(f"\n{len(violations)} architecture violation(s).", file=sys.stderr)
        return 1
    print("Architecture guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
