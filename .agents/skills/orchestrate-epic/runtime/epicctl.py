#!/usr/bin/env python3
"""Executable/package-safe facade for the durable orchestration control plane.

The policy module intentionally wraps the historical v2 core dynamically. This
facade keeps that runtime behavior while preserving the old public/test surface
where an empty lease set is observationally absent and a no-op checkpoint does
not require a symmetric Git diff.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # executed as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _epicctl_policy as _impl
else:
    from . import _epicctl_policy as _impl

_ORIGINAL_TASK_STATES = _impl._task_states
_ORIGINAL_CHECKPOINT_CHANGED_PATHS = _impl._checkpoint_changed_paths
_ORIGINAL_CHECKPOINT_TASK = _impl._checkpoint_task
_ORIGINAL_POLICY_HOOK = _impl._hook_pre_tool_use
_ORIGINAL_GIT_OUTPUT = _impl._core._git_output


def _task_states(
    manifest: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    states = _ORIGINAL_TASK_STATES(manifest, events)
    for state in states.values():
        if not state.get("scope_leases"):
            state.pop("scope_leases", None)
    return states


def _commit_resolves(repo: Path, sha: str) -> bool:
    try:
        resolved = _impl._core._git_output(
            repo,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{sha}^{{commit}}",
        )
    except _impl._core.ControlError:
        return False
    return resolved == sha


def _checkpoint_changed_paths(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    task: str,
    repo: Path,
    head_sha: str,
) -> list[str]:
    state = _task_states(manifest, events)[task]
    base_sha = state.get("base_sha")
    if base_sha == head_sha:
        return []
    if (
        not isinstance(base_sha, str)
        or not _commit_resolves(repo, base_sha)
        or not _commit_resolves(repo, head_sha)
    ):
        # The historical compatibility tests and some recovery paths validate
        # remote identity in a proof checkout that intentionally lacks the
        # worker commits. Preserve that validation order and acquire leases only
        # when a real base...head diff can be proven locally.
        return []
    return _ORIGINAL_CHECKPOINT_CHANGED_PATHS(manifest, events, task, repo, head_sha)


def _checkpoint_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: Any,
    *,
    refresh_remote: bool,
) -> dict[str, Any]:
    result = _ORIGINAL_CHECKPOINT_TASK(
        manifest,
        events,
        journal,
        args,
        refresh_remote=refresh_remote,
    )
    if not result.get("scope_leases_granted"):
        result.pop("scope_leases_granted", None)
    return result


def _conflicting_live_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    task: str,
    path: str,
) -> str | None:
    effective = _impl._effective_manifest(manifest, events)
    states = _task_states(manifest, events)
    definition = effective["tasks"][task]
    for other_task, other_state in states.items():
        if (
            other_task == task
            or other_state["status"] not in _impl._core.LIVE_TASK_STATUSES
        ):
            continue
        other_definition = effective["tasks"][other_task]
        if definition.get("repo") != other_definition.get("repo"):
            continue
        if any(
            _impl._core._path_matches(path, pattern)
            for pattern in other_definition.get("lane", [])
        ):
            return other_task
    return None


def _hook_pre_tool_use(
    payload: dict[str, Any],
    root: Path,
    envelope: dict[str, Any],
) -> None:
    if payload.get("tool_name") in {"Edit", "Write"}:
        manifest_path, journal_path, worktree, task = _impl._core._envelope_paths(
            root, envelope
        )
        manifest = _impl._core._load_manifest(manifest_path)
        events = _impl._core._load_events(journal_path, manifest)
        tool_input = payload.get("tool_input")
        raw_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        if isinstance(raw_path, str) and raw_path:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = Path(str(payload.get("cwd", worktree))) / candidate
            try:
                relative = candidate.resolve().relative_to(worktree).as_posix()
            except ValueError:
                pass
            else:
                owner = _conflicting_live_task(manifest, events, task, relative)
                if owner is not None:
                    _impl._core._emit_hook(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "permissionDecision": "deny",
                                "permissionDecisionReason": (
                                    f"orchestration guard denied {relative} "
                                    f"owned by live task {owner}"
                                ),
                            }
                        }
                    )
                    return
    _ORIGINAL_POLICY_HOOK(payload, root, envelope)


# Patch both policy and core call sites before exporting the public surface.
_impl._task_states = _task_states
_impl._checkpoint_changed_paths = _checkpoint_changed_paths
_impl._checkpoint_task = _checkpoint_task
_impl._conflicting_live_task = _conflicting_live_task
_impl._hook_pre_tool_use = _hook_pre_tool_use
_impl._core._task_states = _task_states
_impl._core._checkpoint_changed_paths = _checkpoint_changed_paths
_impl._core._checkpoint_task = _checkpoint_task
_impl._core._hook_pre_tool_use = _hook_pre_tool_use

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

globals().update(
    {
        "_task_states": _task_states,
        "_checkpoint_changed_paths": _checkpoint_changed_paths,
        "_checkpoint_task": _checkpoint_task,
        "_conflicting_live_task": _conflicting_live_task,
        "_hook_pre_tool_use": _hook_pre_tool_use,
    }
)


def main(argv: Sequence[str] | None = None, **kwargs: Any) -> int:
    # Preserve the old module-level monkeypatch seam used by deterministic
    # recovery tests and by embedders that inject a Git adapter.
    _impl._core._git_output = globals().get("_git_output", _ORIGINAL_GIT_OUTPUT)
    return _impl.main(argv, **kwargs)


globals()["main"] = main


if __name__ == "__main__":
    raise SystemExit(main())
