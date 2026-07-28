#!/usr/bin/env python3
"""Fail fast before spending planner tokens on an epic run.

Every check here exists because its absence once cost a real run. The hook
seam in particular: a guard hook launched by an interpreter that cannot import
its dependencies exits non-zero, and the agent harness then blocks every
Edit/Write -- so the run dies on the first worker edit rather than here.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class PreflightError(RuntimeError):
    """A local prerequisite is missing, stale, or ambiguous."""


def _run(argv: list[str], *, cwd: Path, json_output: bool = False) -> Any:
    try:
        completed = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise PreflightError(f"cannot start {argv[0]}: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PreflightError(f"{shlex.join(argv)} failed: {detail}")
    output = completed.stdout.strip()
    if not json_output:
        return output
    try:
        return json.loads(output) if output else {}
    except json.JSONDecodeError as exc:
        raise PreflightError(f"{shlex.join(argv)} did not return JSON: {output}") from exc


def _executable(*candidates: str | None) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) if os.sep not in candidate else candidate
        if resolved:
            return resolved
    raise PreflightError(
        "Orca is unavailable; set --orca, ORCA_CLI_COMMAND, or install orca/orca-dev/orca-ide"
    )


def _git_state(root: Path, *, branch: str) -> dict[str, str]:
    _run(["git", "fetch", "--quiet", "origin", branch], cwd=root)
    current = _run(["git", "branch", "--show-current"], cwd=root)
    if current != branch:
        raise PreflightError(f"launch checkout must be on {branch}, found {current or 'detached'}")
    if _run(["git", "status", "--porcelain"], cwd=root):
        raise PreflightError("launch checkout is dirty; commit or stash unrelated work first")
    head = _run(["git", "rev-parse", "HEAD"], cwd=root)
    remote = _run(["git", "rev-parse", f"refs/remotes/origin/{branch}"], cwd=root)
    if head != remote:
        raise PreflightError(f"local {branch} {head} is not origin/{branch} {remote}; pull first")
    return {"branch": branch, "head": head, "origin": remote}


def _hook_seam(root: Path) -> dict[str, str]:
    """Invoke each configured hook the way the agent harness invokes it.

    Preflight itself may run under a provisioned interpreter while the harness
    launches hooks through a plain shell with only `$CLAUDE_PROJECT_DIR` set.
    With no active envelope every hook must be a silent no-op: exit 0, no
    stdout, no stderr.
    """
    settings_path = root / ".claude" / "settings.json"
    if not settings_path.is_file():
        return {}
    try:
        hooks = json.loads(settings_path.read_text()).get("hooks", {})
    except ValueError as exc:
        raise PreflightError(f"cannot read {settings_path}: {exc}") from exc

    payload = json.dumps(
        {
            "cwd": str(root),
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(root / "README.md")},
        }
    )
    environment = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    verified: dict[str, str] = {}
    for event, entries in sorted(hooks.items()):
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = hook["command"]
                try:
                    completed = subprocess.run(
                        command,
                        cwd=root,
                        shell=True,  # noqa: S602 - mirrors how the harness runs hooks
                        input=payload,
                        text=True,
                        capture_output=True,
                        check=False,
                        env=environment,
                        timeout=120,
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    raise PreflightError(f"{event} hook could not run: {exc}") from exc
                if completed.returncode != 0:
                    detail = completed.stderr.strip() or completed.stdout.strip()
                    raise PreflightError(
                        f"{event} hook exits {completed.returncode} with no active envelope, so "
                        f"the harness will block every Edit/Write: {detail}"
                    )
                noise = completed.stdout.strip() or completed.stderr.strip()
                if noise:
                    raise PreflightError(
                        f"{event} hook must be silent with no active envelope, emitted: {noise}"
                    )
                verified[event] = command
    return verified


def preflight(*, root: Path, branch: str, orca: str | None, manifest: Path | None) -> dict[str, Any]:
    git_state = _git_state(root, branch=branch)
    _run(["gh", "auth", "status"], cwd=root)
    versions = {"git": _run(["git", "--version"], cwd=root), "uv": _run(["uv", "--version"], cwd=root)}
    executable = _executable(
        orca, os.environ.get("ORCA_CLI_COMMAND"), os.environ.get("ORCA_BIN"), "orca-dev", "orca-ide", "orca"
    )
    result: dict[str, Any] = {
        "git": git_state,
        "hooks": _hook_seam(root),
        "orca": {
            "executable": executable,
            "status": _run([executable, "status", "--json"], cwd=root, json_output=True),
        },
        "versions": versions,
    }
    if manifest is not None:
        if not manifest.is_file():
            raise PreflightError(f"manifest does not exist: {manifest}")
        value = json.loads(manifest.read_text())
        result["manifest"] = {
            "epic": value.get("epic"),
            "run_id": value.get("run_id"),
            "tasks": len(value.get("tasks", {})),
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--branch", default="main")
    parser.add_argument("--orca")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        result = preflight(
            root=args.root.resolve(), branch=args.branch, orca=args.orca, manifest=args.manifest
        )
    except (PreflightError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
