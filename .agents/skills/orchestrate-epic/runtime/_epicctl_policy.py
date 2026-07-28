#!/usr/bin/env python3
"""Public epicctl entry point with live, journaled scope leases.

The large deterministic state machine remains in ``_epicctl_core``. This module
adds one deliberately narrow policy extension: an active worker may acquire an
exact-path lease the first time it edits an otherwise non-conflicting file.
The lease is durable, visible in the task envelope, blocks later conflicting
dispatches while the task is live, and is accepted as part of the task lane.

This removes the old "discover at PR time that the file was not granted"
feedback loop without weakening protected paths or concurrent ownership.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator, Sequence

try:
    from . import _epicctl_core as _core
except ImportError:  # imported as a top-level module
    import _epicctl_core as _core

_BASE_TASK_STATES = _core._task_states
_BASE_READY = _core._ready
_BASE_TASK_CONTRACT = _core._task_contract
_BASE_ACCEPT_TASK = _core._accept_task
_BASE_REVIEW_PACKET = _core._review_packet
_BASE_RECORD_REVIEW = _core._record_review
_BASE_CHECKPOINT_TASK = _core._checkpoint_task
_BASE_HOOK_PRE_TOOL_USE = _core._hook_pre_tool_use
_BASE_APPEND_EVENT = _core._append_event

# The manifest a command was invoked with, while that command is delegating to
# the core through a derived manifest. See ``_append_event`` below.
_PINNED_MANIFEST: dict[str, Any] | None = None


@contextmanager
def _pinned_manifest(manifest: dict[str, Any]) -> Iterator[None]:
    """Preserve the invoked manifest across one derive-and-delegate call."""
    global _PINNED_MANIFEST
    previous = _PINNED_MANIFEST
    _PINNED_MANIFEST = manifest
    try:
        yield
    finally:
        _PINNED_MANIFEST = previous


def _append_event(
    journal: Path,
    manifest: dict[str, Any],
    event_type: str,
    data: dict[str, Any],
    expected_seq: int,
) -> dict[str, Any]:
    """Re-validate the journal against the manifest the run was initialized with.

    The wrappers below hand the core a manifest *derived* from the invoked one:
    per-task model profiles resolved into the core's role slots, and granted
    leases folded into task lanes. That derivation is correct for building a
    packet or a task contract, but its digest is deliberately not the pinned
    digest — and the core re-validates the journal against whatever manifest it
    happens to be holding when it appends. Without this indirection every
    command that appends an event after a derivation fails the digest guard,
    which is every manifest carrying ``model_profiles``.

    The manifest reaches ``_load_events`` for that one identity check and is
    used for nothing else here, so substituting the pinned manifest restores
    the guard's intent rather than weakening it.
    """
    return _BASE_APPEND_EVENT(
        journal,
        manifest if _PINNED_MANIFEST is None else _PINNED_MANIFEST,
        event_type,
        data,
        expected_seq,
    )


def _lease_map(events: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    leases: dict[str, dict[str, str]] = {}
    for event in events:
        event_type = event.get("type")
        if event_type == "scope_lease_granted":
            task = str(event.get("task"))
            path = event.get("path")
            reason = event.get("reason")
            if isinstance(path, str) and path and isinstance(reason, str) and reason:
                leases.setdefault(task, {})[path] = reason
        elif event_type == "scope_lease_released":
            task = str(event.get("task"))
            path = event.get("path")
            if isinstance(path, str):
                leases.setdefault(task, {}).pop(path, None)
    return leases


def _task_states(
    manifest: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    states = _BASE_TASK_STATES(manifest, events)
    leases = _lease_map(events)
    for task, state in states.items():
        state["scope_leases"] = [
            {"path": path, "reason": reason}
            for path, reason in sorted(leases.get(task, {}).items())
        ]
    return states


def _effective_manifest(
    manifest: dict[str, Any], events: list[dict[str, Any]], only: str | None = None
) -> dict[str, Any]:
    """Fold granted leases into task lanes.

    ``only`` restricts the fold to one task. Every per-task derivation must
    pass it: the core digests whatever manifest it is handed into the review
    packet and re-derives that digest to validate the packet later, so folding
    *every* task's leases makes one task's packet depend on its siblings. A
    sibling acquiring an unrelated lease would then invalidate an in-flight
    packet, which has nothing to do with the reviewed task's contract.
    """
    effective = deepcopy(manifest)
    leases = _lease_map(events)
    if only is not None:
        leases = {task: paths for task, paths in leases.items() if task == only}
    for task, paths in leases.items():
        definition = effective.get("tasks", {}).get(task)
        if not isinstance(definition, dict):
            continue
        lane = list(definition.get("lane", []))
        for path in sorted(paths):
            if path not in lane:
                lane.append(path)
        definition["lane"] = lane
    return effective


def _ready(manifest: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    return _BASE_READY(_effective_manifest(manifest, events), events)


def _task_contract(
    manifest: dict[str, Any], task: str, state: dict[str, Any]
) -> dict[str, Any]:
    contract = _BASE_TASK_CONTRACT(manifest, task, state)
    leases = state.get("scope_leases", [])
    if leases:
        contract["scope_leases"] = leases
        effective_lane = list(contract["lane"])
        for lease in leases:
            path = lease["path"]
            if path not in effective_lane:
                effective_lane.append(path)
        contract["lane"] = effective_lane
    definition = manifest["tasks"][task]
    for field in (
        "outcome",
        "decision_boundary",
        "interfaces",
        "uncertainty",
        "worker_profile",
        "reviewer_profile",
    ):
        if field in definition:
            contract[field] = definition[field]
    return json.loads(_core._canonical_json(contract))


def _manifest_for_task(manifest: dict[str, Any], task: str) -> dict[str, Any]:
    """Resolve optional per-task model profiles into the core's v1 role slots."""
    profiles = manifest.get("model_profiles")
    definition = manifest.get("tasks", {}).get(task)
    if not isinstance(profiles, dict) or not isinstance(definition, dict):
        return manifest
    effective = deepcopy(manifest)
    models = effective.setdefault("models", {})
    for role, field in (
        ("worker", "worker_profile"),
        ("reviewer", "reviewer_profile"),
    ):
        profile_name = definition.get(field)
        role_profiles = profiles.get(f"{role}s")
        if (
            isinstance(profile_name, str)
            and isinstance(role_profiles, dict)
            and isinstance(role_profiles.get(profile_name), dict)
        ):
            models[role] = deepcopy(role_profiles[profile_name])
    return effective


def _accept_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    github_collector: _core.GitHubCollector,
) -> dict[str, Any]:
    task = str(args.task)
    task_manifest = _manifest_for_task(_effective_manifest(manifest, events, task), task)
    with _pinned_manifest(manifest):
        return _BASE_ACCEPT_TASK(task_manifest, events, journal, args, github_collector)


def _review_packet(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    github_collector: _core.GitHubCollector,
) -> dict[str, Any]:
    task = str(args.task)
    task_manifest = _manifest_for_task(_effective_manifest(manifest, events, task), task)
    with _pinned_manifest(manifest):
        return _BASE_REVIEW_PACKET(task_manifest, events, journal, args, github_collector)


def _record_review(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    # Derive exactly as ``_review_packet`` does. Validating an issued packet
    # against a differently-derived manifest rejects every packet the moment a
    # lease exists, because the packet's ``manifest_digest`` and its
    # ``task_contract`` are both taken from the lease-folded manifest.
    task = str(args.task)
    task_manifest = _manifest_for_task(_effective_manifest(manifest, events, task), task)
    with _pinned_manifest(manifest):
        return _BASE_RECORD_REVIEW(task_manifest, events, journal, args)


def _checkpoint_changed_paths(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    task: str,
    repo: Path,
    head_sha: str,
) -> list[str]:
    state = _task_states(manifest, events)[task]
    base_sha = state.get("base_sha")
    if not isinstance(base_sha, str) or not base_sha:
        raise _core.ControlError(f"task {task} is missing its pinned base SHA")
    raw = _core._git_output(
        repo,
        "diff",
        "--name-only",
        "-z",
        "--diff-filter=ACDMRTUXB",
        f"{base_sha}...{head_sha}",
    )
    return sorted({path for path in raw.split("\0") if path})


def _checkpoint_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    *,
    refresh_remote: bool,
) -> dict[str, Any]:
    task = str(args.task)
    if task not in manifest["tasks"]:
        raise _core.ControlError(f"unknown task: {task}")
    states = _task_states(manifest, events)
    if states[task]["status"] != "active":
        raise _core.ControlError(
            f"task {task} is not active (status: {states[task]['status']})"
        )
    changed = _checkpoint_changed_paths(manifest, events, task, args.repo, args.sha)
    definition = manifest["tasks"][task]
    existing = _lease_map(events).get(task, {})
    candidates = [
        path
        for path in changed
        if path not in existing
        and not any(
            _core._path_matches(path, pattern)
            for pattern in definition.get("lane", [])
        )
    ]

    # Validate the entire discovered scope before writing any lease event. This
    # keeps a bad checkpoint from partially broadening the task.
    for path in candidates:
        matched = _hard_forbidden(manifest, task, path)
        if matched is not None:
            raise _core.ControlError(
                f"checkpoint scope includes hard-forbidden path {path} (matched {matched})"
            )
        owner = _conflicting_live_task(manifest, events, task, path)
        if owner is not None:
            raise _core.ControlError(
                f"checkpoint scope path {path} conflicts with live task {owner}",
                task=task,
                path=path,
                conflicting_task=owner,
                next_action="wait_or_planner_handoff",
            )

    current_events = events
    seq = args.expected_seq
    granted: list[str] = []
    for path in candidates:
        result = _grant_scope_lease(
            manifest,
            current_events,
            journal,
            task=task,
            raw_path=path,
            reason="automatic checkpoint lease from the complete base...head diff",
            expected_seq=seq,
            source="checkpoint_diff",
        )
        seq = int(result["seq"])
        granted.append(path)
        current_events = _core._load_events(journal, manifest)

    forwarded = argparse.Namespace(**vars(args))
    forwarded.expected_seq = seq
    result = _BASE_CHECKPOINT_TASK(
        manifest,
        current_events,
        journal,
        forwarded,
        refresh_remote=refresh_remote,
    )
    result["scope_leases_granted"] = granted
    return result


def _resolve_model_route(
    manifest: dict[str, Any],
    *,
    role: str,
    task: str | None,
) -> dict[str, Any]:
    profiles = manifest.get("model_profiles")
    routing = manifest.get("model_routing")
    if not isinstance(profiles, dict) or not isinstance(routing, dict):
        legacy_role = "planner" if role.startswith("planner") else role
        identity = manifest.get("models", {}).get(legacy_role)
        if not isinstance(identity, dict):
            raise _core.ControlError(f"manifest has no model route for {role}")
        return {"identity": identity, "profile": legacy_role, "role": role, "task": task}

    if role == "planner":
        profile = routing.get("planner_primary")
        group = "planners"
    elif role == "planner-escalation":
        profile = routing.get("planner_escalation")
        group = "planners"
    else:
        if task is None or task not in manifest.get("tasks", {}):
            raise _core.ControlError(f"model route {role} requires a known task")
        definition = manifest["tasks"][task]
        field = "worker_profile" if role == "worker" else "reviewer_profile"
        profile = definition.get(field)
        group = "workers" if role == "worker" else "reviewers"
    if not isinstance(profile, str):
        raise _core.ControlError(f"manifest route {role} has no profile")
    identities = profiles.get(group)
    if not isinstance(identities, dict) or not isinstance(identities.get(profile), dict):
        raise _core.ControlError(f"manifest route {role} names unknown profile {profile!r}")
    return {
        "identity": identities[profile],
        "profile": profile,
        "role": role,
        "task": task,
    }


def _normalize_exact_path(raw: str) -> str:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise _core.ControlError("scope lease path must be repository-relative")
    normalized = candidate.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    # `Path.as_posix()` has already stripped any trailing separator and turned
    # "" / "./" into ".", so both of these must be tested against the raw
    # request: otherwise "src/" leases a directory as though it named one exact
    # file, and "" leases the repository root.
    if (
        not normalized
        or normalized == "."
        or raw.endswith("/")
        or any(token in normalized for token in ("*", "?", "["))
    ):
        raise _core.ControlError("automatic scope leases must name one exact file path")
    return normalized


def _hard_forbidden(manifest: dict[str, Any], task: str, path: str) -> str | None:
    definition = manifest["tasks"][task]
    patterns = [
        *manifest.get("protected_paths", []),
        *manifest.get("no_go_paths", []),
        *definition.get("forbidden_paths", []),
    ]
    return next((pattern for pattern in patterns if _core._path_matches(path, pattern)), None)


def _conflicting_live_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    task: str,
    path: str,
) -> str | None:
    effective = _effective_manifest(manifest, events)
    states = _task_states(manifest, events)
    definition = effective["tasks"][task]
    for other_task, other_state in states.items():
        if other_task == task or other_state["status"] not in _core.LIVE_TASK_STATUSES:
            continue
        other_definition = effective["tasks"][other_task]
        if definition.get("repo") != other_definition.get("repo"):
            continue
        if any(
            _core._path_matches(path, pattern)
            for pattern in other_definition.get("lane", [])
        ):
            return other_task
    return None


def _grant_scope_lease(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    *,
    task: str,
    raw_path: str,
    reason: str,
    expected_seq: int,
    source: str,
) -> dict[str, Any]:
    if task not in manifest["tasks"]:
        raise _core.ControlError(f"unknown task: {task}")
    states = _task_states(manifest, events)
    if states[task]["status"] != "active":
        raise _core.ControlError(
            f"task {task} must be active to acquire a scope lease "
            f"(status: {states[task]['status']})"
        )
    path = _normalize_exact_path(raw_path)
    definition = manifest["tasks"][task]
    if any(_core._path_matches(path, pattern) for pattern in definition.get("lane", [])):
        return {
            "path": path,
            "reason": "already in the task's base lane",
            "seq": events[-1]["seq"],
            "status": "already_owned",
            "task": task,
        }
    existing = _lease_map(events).get(task, {}).get(path)
    if existing is not None:
        return {
            "path": path,
            "reason": existing,
            "seq": events[-1]["seq"],
            "status": "already_leased",
            "task": task,
        }
    matched = _hard_forbidden(manifest, task, path)
    if matched is not None:
        raise _core.ControlError(
            f"scope lease denied for hard-forbidden path {path} (matched {matched})"
        )
    owner = _conflicting_live_task(manifest, events, task, path)
    if owner is not None:
        raise _core.ControlError(
            f"scope lease for {path} conflicts with live task {owner}",
            task=task,
            path=path,
            conflicting_task=owner,
            next_action="wait_or_planner_handoff",
        )
    if not reason.strip():
        raise _core.ControlError("scope lease reason must be non-empty")
    future_claimants = sorted(
        other_task
        for other_task, other_definition in manifest["tasks"].items()
        if other_task != task
        and definition.get("repo") == other_definition.get("repo")
        and any(
            _core._path_matches(path, pattern)
            for pattern in other_definition.get("lane", [])
        )
    )
    event = _core._append_event(
        journal,
        manifest,
        "scope_lease_granted",
        {
            "task": task,
            "path": path,
            "reason": reason.strip(),
            "source": source,
            "serializes": future_claimants,
        },
        expected_seq,
    )
    return {
        "path": path,
        "reason": reason.strip(),
        "seq": event["seq"],
        "serializes": future_claimants,
        "status": "granted",
        "task": task,
    }


def _hook_pre_tool_use(
    payload: dict[str, Any],
    root: Path,
    envelope: dict[str, Any],
) -> None:
    if payload.get("tool_name") not in {"Edit", "Write"}:
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return
    manifest_path, journal_path, worktree, task = _core._envelope_paths(root, envelope)
    manifest = _core._load_manifest(manifest_path)
    events = _core._load_events(journal_path, manifest)
    states = _task_states(manifest, events)
    state = states.get(task)
    if state is None or state["status"] != "active":
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return
    raw_path = tool_input.get("file_path")
    if not isinstance(raw_path, str) or not raw_path:
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = Path(str(payload.get("cwd", worktree))) / candidate
    try:
        relative = candidate.resolve().relative_to(worktree).as_posix()
    except ValueError:
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return

    definition = manifest["tasks"][task]
    if any(_core._path_matches(relative, pattern) for pattern in definition.get("lane", [])):
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return
    if relative in _lease_map(events).get(task, {}):
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return
    matched = _hard_forbidden(manifest, task, relative)
    if matched is not None:
        _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)
        return
    owner = _conflicting_live_task(manifest, events, task, relative)
    if owner is not None:
        _core._emit_hook(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"orchestration guard denied {relative}: live task {owner} "
                        "holds the path. Wait for merge or open a planner handoff."
                    ),
                }
            }
        )
        return

    # The hook is already serialized by epicctl's journal lock. If another
    # mutation wins the optimistic race, reload once and retry only when the
    # path is still conflict-free.
    for attempt in range(2):
        try:
            _grant_scope_lease(
                manifest,
                events,
                journal_path,
                task=task,
                raw_path=relative,
                reason=f"automatic first-write lease for {payload.get('tool_name')}",
                expected_seq=events[-1]["seq"],
                source="claude_pre_tool_use",
            )
            break
        except _core.ControlError as exc:
            if "journal advanced" not in str(exc) or attempt == 1:
                raise
            events = _core._load_events(journal_path, manifest)

    _BASE_HOOK_PRE_TOOL_USE(payload, root, envelope)


def _scope_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage exact-path live scope leases.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    request = subparsers.add_parser("lease-request")
    request.add_argument("task")
    request.add_argument("--path", required=True)
    request.add_argument("--reason", required=True)
    request.add_argument("--expected-seq", type=int, required=True)

    listing = subparsers.add_parser("lease-list")
    listing.add_argument("task", nargs="?")

    declarations = subparsers.add_parser("lease-declarations")
    declarations.add_argument("task")
    declarations.add_argument("--output", type=Path, required=True)

    route = subparsers.add_parser("model-route")
    route.add_argument(
        "--role",
        choices=("planner", "planner-escalation", "worker", "reviewer"),
        required=True,
    )
    route.add_argument("--task")
    return parser


def _scope_main(argv: Sequence[str]) -> int:
    args = _scope_parser().parse_args(argv)
    try:
        manifest = _core._load_manifest(args.manifest)
        events = _core._load_events(args.journal, manifest)
        if args.command == "lease-request":
            result = _grant_scope_lease(
                manifest,
                events,
                args.journal,
                task=str(args.task),
                raw_path=args.path,
                reason=args.reason,
                expected_seq=args.expected_seq,
                source="worker_request",
            )
        elif args.command == "lease-list":
            leases = _lease_map(events)
            if args.task is not None:
                leases = {str(args.task): leases.get(str(args.task), {})}
            result = {"leases": leases, "seq": events[-1]["seq"]}
        elif args.command == "model-route":
            result = {
                **_resolve_model_route(
                    manifest, role=args.role, task=str(args.task) if args.task else None
                ),
                "seq": events[-1]["seq"],
            }
        else:
            task = str(args.task)
            if task not in manifest["tasks"]:
                raise _core.ControlError(f"unknown task: {task}")
            declarations = _lease_map(events).get(task, {})
            _core._write_json_atomic(args.output, declarations)
            result = {
                "output": str(args.output),
                "paths": sorted(declarations),
                "seq": events[-1]["seq"],
                "task": task,
            }
    except _core.ControlError as exc:
        print(json.dumps({"error": str(exc), **exc.details}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


# Patch the core's internal call sites once. Existing behavioral tests that
# import ``scripts.epicctl`` still see the full historical API below.
_core._task_states = _task_states
_core._ready = _ready
_core._task_contract = _task_contract
_core._accept_task = _accept_task
_core._review_packet = _review_packet
_core._record_review = _record_review
_core._checkpoint_task = _checkpoint_task
_core._hook_pre_tool_use = _hook_pre_tool_use
_core._append_event = _append_event


def main(argv: Sequence[str] | None = None, **kwargs: Any) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if any(
        command in arguments
        for command in ("lease-request", "lease-list", "lease-declarations", "model-route")
    ):
        return _scope_main(arguments)
    return _core.main(arguments, **kwargs)


for _name in dir(_core):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(_core, _name))


if __name__ == "__main__":
    raise SystemExit(main())
