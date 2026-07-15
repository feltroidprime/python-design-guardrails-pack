#!/usr/bin/env python3
"""Run the project-pinned Codex Langfuse hook from the repository root."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import cast

EXPECTED_ARGUMENT_COUNT = 3
HOOK_STATUS = "Uploading Codex trace to Langfuse"


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    mapping = cast("dict[object, object]", value)
    return {key: item for key, item in mapping.items() if isinstance(key, str)}


def _groups(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    values = cast("list[object]", value)
    return [_mapping(cast("object", item)) for item in values if isinstance(item, dict)]


def _is_managed(group: dict[str, object]) -> bool:
    return any(
        hook.get("statusMessage") == HOOK_STATUS
        and "agent_observability_codex_hook.py" in str(hook.get("command", ""))
        for hook in _groups(group.get("hooks"))
    )


def codex_hook_group(root: Path, revision: str) -> dict[str, object]:
    checkout = root / ".agent-observability" / f"codex-plugin-{revision}"
    entrypoint = checkout / "plugins" / "tracing" / "dist" / "index.mjs"
    runner = root / "scripts" / "agent_observability_codex_hook.py"
    command = (
        f"python3 {shlex.quote(str(runner))} {shlex.quote(str(entrypoint))} {shlex.quote(revision)}"
    )
    command_windows = f'py -3 "{runner}" "{entrypoint}" "{revision}"'
    return {
        "hooks": [
            {
                "command": command,
                "command_windows": command_windows,
                "statusMessage": HOOK_STATUS,
                "timeout": 30,
                "type": "command",
            }
        ]
    }


def merge_codex_hook(
    config: dict[str, object],
    managed_group: dict[str, object],
) -> dict[str, object]:
    merged = dict(config)
    hooks = _mapping(merged.get("hooks"))
    unrelated = [group for group in _groups(hooks.get("Stop")) if not _is_managed(group)]
    hooks["Stop"] = [*unrelated, managed_group]
    merged["hooks"] = hooks
    return merged


def remove_codex_hook(config: dict[str, object]) -> dict[str, object]:
    cleaned = dict(config)
    hooks = _mapping(cleaned.get("hooks"))
    remaining = [group for group in _groups(hooks.get("Stop")) if not _is_managed(group)]
    if remaining:
        hooks["Stop"] = remaining
    else:
        _ = hooks.pop("Stop", None)
    if hooks:
        cleaned["hooks"] = hooks
    else:
        _ = cleaned.pop("hooks", None)
    return cleaned


def codex_hook_is_configured(
    config: dict[str, object],
    managed_group: dict[str, object],
) -> bool:
    hooks = _mapping(config.get("hooks"))
    return managed_group in _groups(hooks.get("Stop"))


def main() -> int:
    if len(sys.argv) != EXPECTED_ARGUMENT_COUNT:
        return 0
    root = Path(__file__).resolve().parents[1]
    checkout_root = root / ".agent-observability"
    entrypoint = Path(sys.argv[1]).resolve()
    revision = sys.argv[2]
    checkout = checkout_root / f"codex-plugin-{revision}"
    if (
        entrypoint.parents[3] != checkout
        or entrypoint.name != "index.mjs"
        or not entrypoint.is_file()
        or not (root / ".codex" / "langfuse.json").is_file()
    ):
        return 0
    node = shutil.which("node")
    git = shutil.which("git")
    if node is None or git is None:
        return 0
    head = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    cleanliness = subprocess.run(
        [git, "status", "--porcelain"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    if (
        head.returncode != 0
        or head.stdout.strip() != revision
        or cleanliness.returncode != 0
        or cleanliness.stdout.strip()
    ):
        return 0
    try:
        os.chdir(root)
        os.execv(node, (node, str(entrypoint)))
    except OSError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
