#!/usr/bin/env python3
"""Claude Code PostToolUse hook: reject reminder comments as they are written.

The template's ARCH031 rule is the single source of the patterns; this hook
delivers the same verdict at edit time for the pack's own Python files, so the
correction arrives the moment the comment is written instead of at push time.
"""

import json
from pathlib import Path
import sys
import tokenize

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "template"))

from scripts.review_discipline import REMINDER_PATTERNS  # noqa: E402


def edited_python_file(payload: dict) -> Path | None:
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    raw = tool_input.get("file_path") or tool_response.get("filePath")
    if not raw:
        return None
    path = Path(raw)
    if path.suffix != ".py" or not path.is_file():
        return None
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        return None
    return path


def reminder_comments(path: Path) -> list[tuple[int, str]]:
    with tokenize.open(path) as handle:
        tokens = list(tokenize.generate_tokens(handle.readline))
    return [
        (token.start[0], token.string.strip())
        for token in tokens
        if token.type == tokenize.COMMENT
        and "ARCH-EXCEPTION" not in token.string
        and any(pattern.search(token.string) for pattern in REMINDER_PATTERNS)
    ]


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0
    path = edited_python_file(payload)
    if path is None:
        return 0
    try:
        offending = reminder_comments(path)
    except (OSError, SyntaxError, tokenize.TokenError):
        return 0
    if not offending:
        return 0
    listing = "\n".join(
        f"  {path.relative_to(REPO_ROOT)}:{line}: {text}" for line, text in offending
    )
    print(
        "Reminder comment detected (it schedules manual upkeep):\n"
        f"{listing}\n"
        "Derive the value from its source of truth or enforce the invariant "
        "with a test or gate check, then delete the comment. See "
        "DESIGN_GUARDRAILS.md, 'Invariants entrusted to human memory' (ARCH031).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
