#!/usr/bin/env python3
"""Deterministic control plane for durable epic orchestration runs.

Its hash chain is an orchestration control journal outside the Conductor runtime.
It is not the engine's committed decision journal.
"""

from __future__ import annotations

import argparse
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

try:
    from . import github_evidence
except ImportError:
    import github_evidence

ZERO_HASH = "0" * 64
MAX_GOAL_TREE_DEPTH = 8
MAX_PACKET_PRIOR_REVIEWS = 4
LIVE_TASK_STATUSES = {
    "accepted",
    "active",
    "merge_pending",
    "needs_planner",
    "redispatch",
    "restart_required",
}
GitHubCollector = Callable[..., dict[str, Any]]
GitHubMerger = Callable[..., dict[str, Any]]
GitHubMergeStateCollector = Callable[..., dict[str, Any]]


class ControlError(Exception):
    """A caller-visible control-plane error."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.details = details


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlError(f"{path} must contain a JSON object")
    return value


def _goal_paths(manifest: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    paths: dict[str, list[dict[str, str]]] = {}
    node_ids: set[str] = set()

    def visit(
        node: Any,
        ancestors: list[dict[str, str]],
        depth: int,
    ) -> None:
        if not isinstance(node, dict):
            raise ControlError(f"manifest goal_tree child at depth {depth} must be an object")
        if depth > MAX_GOAL_TREE_DEPTH:
            raise ControlError(
                "manifest goal_tree exceeds maximum depth "
                f"{MAX_GOAL_TREE_DEPTH} at node {node.get('id', '<unknown>')}"
            )
        keys = set(node)
        if keys not in ({"id", "task"}, {"id", "goal", "children"}):
            node_label = node.get("id", "<unknown>")
            raise ControlError(
                f"manifest goal_tree node {node_label} must be exactly an internal "
                "node {id, goal, children} or leaf {id, task}"
            )
        node_id = node["id"]
        if not isinstance(node_id, str) or not node_id.strip():
            raise ControlError("manifest goal_tree node id must be a non-empty string")
        if node_id in node_ids:
            raise ControlError(f"manifest goal_tree node id appears more than once: {node_id}")
        node_ids.add(node_id)
        if "task" in node:
            task = node["task"]
            if not isinstance(task, str) or not task.strip():
                raise ControlError(
                    f"manifest goal_tree leaf {node_id} task must be a non-empty string"
                )
            if task not in manifest["tasks"]:
                raise ControlError(f"manifest goal_tree references unknown task: {task}")
            if task in paths:
                raise ControlError(f"manifest goal_tree task appears more than once: {task}")
            paths[task] = ancestors
            return
        goal_text = node["goal"]
        if not isinstance(goal_text, str) or not goal_text.strip():
            raise ControlError(
                f"manifest goal_tree internal node {node_id} goal must be a non-empty string"
            )
        children = node["children"]
        if not isinstance(children, list) or not children:
            raise ControlError(
                f"manifest goal_tree internal node {node_id} children must be a non-empty array"
            )
        goal = {"id": node_id, "goal": goal_text}
        for child in children:
            visit(child, [*ancestors, goal], depth + 1)

    visit(manifest["goal_tree"], [], 0)
    missing = sorted(set(manifest["tasks"]) - set(paths), key=_task_sort_key)
    if missing:
        raise ControlError(f"manifest goal_tree is missing task leaves: {', '.join(missing)}")
    return paths


def _validate_task_initial(
    task: str,
    initial: Any,
) -> tuple[str, str | None]:
    if not isinstance(initial, dict):
        raise ControlError(f"task {task} initial must be an object")
    status = initial.get("status", "pending")
    if status not in {"pending", "merged"}:
        raise ControlError(f"task {task} initial status must be pending or merged")
    expected_keys = {"status", "merge_sha"} if status == "merged" else set(initial) & {"status"}
    if set(initial) != expected_keys:
        raise ControlError(f"task {task} initial has an invalid closed schema")
    if status == "pending":
        return status, None
    merge_sha = initial["merge_sha"]
    if not isinstance(merge_sha, str) or re.fullmatch(r"[0-9a-f]{40}", merge_sha) is None:
        raise ControlError(f"task {task} initial.merge_sha must be a full lowercase 40-hex Git SHA")
    return status, merge_sha


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest = _load_json(path)
    if manifest.get("schema_version") != 1:
        raise ControlError("manifest schema_version must be 1")
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"].strip():
        raise ControlError("manifest run_id must be a non-empty string")
    epoch = manifest.get("epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1:
        raise ControlError("manifest epoch must be a positive integer")
    predecessor_digest = manifest.get("predecessor_manifest_digest")
    if epoch == 1:
        if predecessor_digest is not None:
            raise ControlError("manifest epoch 1 must have null predecessor_manifest_digest")
    elif (
        not isinstance(predecessor_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", predecessor_digest) is None
    ):
        raise ControlError(
            "manifest successor epoch needs a lowercase SHA-256 predecessor_manifest_digest"
        )
    source_main_sha = manifest.get("source_main_sha")
    if source_main_sha is not None and (
        not isinstance(source_main_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_main_sha) is None
    ):
        raise ControlError("manifest source_main_sha must be a full lowercase 40-hex Git SHA")
    if "sources" in manifest:
        sources = manifest["sources"]
        expected_source_keys = {
            "authority",
            "dispatch_plan_sha256",
            "epic_issue_body_sha256",
            "github_issue_snapshot_sha256",
            "main_sha",
        }
        if not isinstance(sources, dict) or set(sources) != expected_source_keys:
            raise ControlError("manifest sources has an invalid closed schema")
        if sources["authority"] not in {"github_live", "recorded_replay"}:
            raise ControlError("manifest sources.authority is invalid")
        for field in (
            "dispatch_plan_sha256",
            "epic_issue_body_sha256",
            "github_issue_snapshot_sha256",
        ):
            if (
                not isinstance(sources[field], str)
                or re.fullmatch(r"[0-9a-f]{64}", sources[field]) is None
            ):
                raise ControlError(f"manifest sources.{field} must be a SHA-256 digest")
        if (
            not isinstance(sources["main_sha"], str)
            or re.fullmatch(r"[0-9a-f]{40}", sources["main_sha"]) is None
            or sources["main_sha"] != source_main_sha
        ):
            raise ControlError("manifest sources.main_sha must equal the full source_main_sha")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, dict) or not tasks:
        raise ControlError("manifest tasks must be a non-empty object")
    if not all(isinstance(task, str) and task.strip() for task in tasks):
        raise ControlError("manifest task ids must be non-empty strings")
    if not isinstance(manifest.get("goal_tree"), dict):
        raise ControlError("manifest goal_tree must be an object")
    _goal_paths(manifest)
    max_concurrent = manifest.get("max_concurrent")
    if (
        isinstance(max_concurrent, bool)
        or not isinstance(max_concurrent, int)
        or max_concurrent < 1
    ):
        raise ControlError("manifest max_concurrent must be a positive integer")
    require_ci = manifest.get("require_ci", True)
    if not isinstance(require_ci, bool):
        raise ControlError("manifest require_ci must be a boolean")
    base_ref = manifest.get("base_ref", "main")
    if not isinstance(base_ref, str) or not base_ref.strip():
        raise ControlError("manifest base_ref must be a non-empty branch name")
    rejection_limit = manifest.get("max_same_finding_rejections", 2)
    if (
        isinstance(rejection_limit, bool)
        or not isinstance(rejection_limit, int)
        or rejection_limit < 1
    ):
        raise ControlError("manifest max_same_finding_rejections must be a positive integer")
    total_rejection_limit = manifest.get("max_review_rejections", 4)
    if (
        isinstance(total_rejection_limit, bool)
        or not isinstance(total_rejection_limit, int)
        or total_rejection_limit < 1
    ):
        raise ControlError("manifest max_review_rejections must be a positive integer")
    models = manifest.get("models")
    if not isinstance(models, dict):
        raise ControlError("manifest models must be an object")
    for role in ("planner", "worker", "reviewer"):
        identity = models.get(role)
        if (
            not isinstance(identity, dict)
            or not isinstance(identity.get("family"), str)
            or not identity["family"].strip()
            or not isinstance(identity.get("model"), str)
            or not identity["model"].strip()
        ):
            raise ControlError(f"manifest models.{role} needs non-empty family and model strings")
    worker_family = models["worker"]["family"]
    reviewer_family = models["reviewer"]["family"]
    if worker_family == reviewer_family:
        raise ControlError("manifest reviewer must use a different model family from the worker")
    checks = manifest.get("checks", [])
    if not isinstance(checks, list):
        raise ControlError("manifest checks must be an array")
    check_names: set[str] = set()
    for check in checks:
        if not isinstance(check, dict):
            raise ControlError("each manifest check must be an object")
        name = check.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ControlError("each manifest check needs a non-empty name")
        if name in check_names:
            raise ControlError(f"duplicate manifest check name: {name}")
        check_names.add(name)
        command = check.get("command")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(argument, str) and argument for argument in command)
        ):
            raise ControlError(f"check {name} command must be a non-empty string array")
    for task, definition in tasks.items():
        if not isinstance(definition, dict):
            raise ControlError(f"task {task} definition must be an object")
        if not isinstance(definition.get("repo"), str) or not definition["repo"].strip():
            raise ControlError(f"task {task} repo must be a non-empty string")
        if definition.get("risk") not in {"mechanical", "novel"}:
            raise ControlError(f"task {task} risk must be mechanical or novel")
        lane = definition.get("lane")
        if (
            not isinstance(lane, list)
            or not lane
            or not all(isinstance(pattern, str) and pattern for pattern in lane)
        ):
            raise ControlError(f"task {task} lane must be a non-empty string array")
        dependencies = definition.get("depends_on", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(dependency, str) and dependency for dependency in dependencies
        ):
            raise ControlError(f"task {task} depends_on must be a string array")
        if len(dependencies) != len(set(dependencies)):
            raise ControlError(f"task {task} depends_on contains duplicates")
        required_checks = definition.get("required_checks", [check["name"] for check in checks])
        if not isinstance(required_checks, list) or not all(
            isinstance(name, str) and name for name in required_checks
        ):
            raise ControlError(f"task {task} required_checks must be a string array")
        for name in required_checks:
            if name not in check_names:
                raise ControlError(f"task {task} references unknown required check: {name}")
        forbidden = definition.get("forbidden_paths", [])
        if not isinstance(forbidden, list) or not all(
            isinstance(pattern, str) and pattern for pattern in forbidden
        ):
            raise ControlError(f"task {task} forbidden_paths must be a string array")
        initial_status, _initial_merge_sha = _validate_task_initial(
            task,
            definition.get("initial", {}),
        )
        if initial_status != "merged":
            criteria = definition.get("acceptance_criteria")
            if (
                not isinstance(criteria, list)
                or not criteria
                or not all(
                    isinstance(criterion, str) and criterion.strip() for criterion in criteria
                )
            ):
                raise ControlError(
                    f"task {task} acceptance_criteria must be a non-empty string array"
                )
    unknown_dependencies = sorted(
        {
            str(dependency)
            for task in tasks.values()
            for dependency in task.get("depends_on", [])
            if str(dependency) not in tasks
        }
    )
    if unknown_dependencies:
        raise ControlError(f"unknown task dependencies: {', '.join(unknown_dependencies)}")
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(task: str) -> None:
        if task in visiting:
            start = visiting.index(task)
            cycle = [*visiting[start:], task]
            raise ControlError(
                "manifest task dependency graph contains a cycle: " + " -> ".join(cycle)
            )
        if task in visited:
            return
        visiting.append(task)
        for dependency in tasks[task].get("depends_on", []):
            visit(dependency)
        visiting.pop()
        visited.add(task)

    for task in tasks:
        visit(str(task))
    barriers = manifest.get("barriers", [])
    if not isinstance(barriers, list):
        raise ControlError("manifest barriers must be an array")
    for barrier in barriers:
        if not isinstance(barrier, dict):
            raise ControlError("each manifest barrier must be an object")
        gate = barrier.get("task")
        if not isinstance(gate, str) or gate not in tasks:
            raise ControlError(f"barrier task {gate} is unknown")
        blocked = barrier.get("blocks")
        if not isinstance(blocked, list) or not all(isinstance(task, str) for task in blocked):
            raise ControlError(f"barrier task {gate} blocks must be a string array")
        for blocked_task in blocked:
            if blocked_task not in tasks:
                raise ControlError(f"barrier blocked task {blocked_task} is unknown")
    for field in ("protected_paths", "no_go_paths"):
        patterns = manifest.get(field, [])
        if not isinstance(patterns, list) or not all(
            isinstance(pattern, str) and pattern for pattern in patterns
        ):
            raise ControlError(f"manifest {field} must be a string array")
    return manifest


def _event_hash(event_without_hash: dict[str, Any]) -> str:
    return _digest(event_without_hash)


def _load_events(journal: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if not journal.exists():
        raise ControlError(f"journal does not exist: {journal}; run init first")
    events: list[dict[str, Any]] = []
    previous = ZERO_HASH
    try:
        lines = journal.read_text().splitlines()
    except OSError as exc:
        raise ControlError(f"cannot read journal {journal}: {exc}") from exc
    for expected_seq, line in enumerate(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ControlError(f"journal line {expected_seq + 1} is invalid JSON") from exc
        if not isinstance(event, dict):
            raise ControlError(f"journal line {expected_seq + 1} is not an object")
        claimed_hash = event.pop("hash", None)
        if event.get("seq") != expected_seq:
            raise ControlError(f"journal sequence break at line {expected_seq + 1}")
        if event.get("prev_hash") != previous:
            raise ControlError(f"journal hash-chain break at line {expected_seq + 1}")
        actual_hash = _event_hash(event)
        if claimed_hash != actual_hash:
            raise ControlError(f"journal content hash mismatch at line {expected_seq + 1}")
        event["hash"] = claimed_hash
        events.append(event)
        previous = claimed_hash
    if not events or events[0].get("type") != "run_initialized":
        raise ControlError("journal is missing run_initialized")
    if events[0].get("manifest_digest") != _digest(manifest):
        raise ControlError("manifest changed after this run was initialized")
    return events


def _write_text_atomic(path: Path, encoded: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _write_new_journal(journal: Path, event: dict[str, Any]) -> None:
    lock_path = journal.with_suffix(f"{journal.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if journal.exists():
            raise ControlError(f"journal already exists: {journal}")
        _write_text_atomic(journal, _canonical_json(event) + "\n")


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _append_event(
    journal: Path,
    manifest: dict[str, Any],
    event_type: str,
    data: dict[str, Any],
    expected_seq: int,
) -> dict[str, Any]:
    lock_path = journal.with_suffix(f"{journal.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        events = _load_events(journal, manifest)
        current_seq = events[-1]["seq"]
        if current_seq != expected_seq:
            raise ControlError(
                f"journal advanced: expected seq {expected_seq}, found {current_seq}"
            )
        return _append_event_under_lock(journal, events, event_type, data)


def _append_event_under_lock(
    journal: Path,
    events: list[dict[str, Any]],
    event_type: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    if any(event["type"] == "successor_epoch_reserved" for event in events):
        raise ControlError("journal is sealed by successor_epoch_reserved and cannot be mutated")
    event = {
        "seq": events[-1]["seq"] + 1,
        "prev_hash": events[-1]["hash"],
        "type": event_type,
        **data,
    }
    event["hash"] = _event_hash(event)
    try:
        prefix = journal.read_text()
    except OSError as exc:
        raise ControlError(f"cannot read journal {journal} for append: {exc}") from exc
    if prefix and not prefix.endswith("\n"):
        raise ControlError(f"journal {journal} has a torn final record")
    _write_text_atomic(journal, prefix + _canonical_json(event) + "\n")
    return event


def _initial_event(
    manifest: dict[str, Any],
    *,
    lineage: dict[str, Any],
) -> dict[str, Any]:
    event = {
        "seq": 0,
        "prev_hash": ZERO_HASH,
        "type": "run_initialized",
        "run_id": manifest.get("run_id"),
        "epoch": manifest["epoch"],
        "manifest_digest": _digest(manifest),
        **lineage,
    }
    event["hash"] = _event_hash(event)
    return event


def _validate_init_lineage(
    manifest: dict[str, Any],
    *,
    predecessor_manifest_path: Path | None,
    predecessor_journal_path: Path | None,
    successor_journal_path: Path,
) -> dict[str, Any]:
    epoch = manifest["epoch"]
    if epoch == 1:
        if predecessor_manifest_path is not None or predecessor_journal_path is not None:
            raise ControlError("epoch 1 init must not supply predecessor files")
        return {}
    if predecessor_manifest_path is None or predecessor_journal_path is None:
        raise ControlError(
            "successor epoch init requires --predecessor-manifest and --predecessor-journal"
        )
    resolved_predecessor_journal = predecessor_journal_path.resolve()
    resolved_successor_journal = successor_journal_path.resolve()
    if resolved_predecessor_journal == resolved_successor_journal:
        raise ControlError("successor journal must differ from the predecessor journal")
    predecessor = _load_manifest(predecessor_manifest_path)
    if predecessor["epoch"] + 1 != epoch:
        raise ControlError(
            f"successor epoch {epoch} must immediately follow predecessor epoch "
            f"{predecessor['epoch']}"
        )
    if predecessor["run_id"] == manifest["run_id"]:
        raise ControlError("successor epoch must use a new run_id")
    if predecessor.get("epic") != manifest.get("epic"):
        raise ControlError("successor epoch must retain the predecessor epic identity")
    predecessor_digest = _digest(predecessor)
    if predecessor_digest != manifest["predecessor_manifest_digest"]:
        raise ControlError(
            "successor predecessor_manifest_digest does not match --predecessor-manifest"
        )
    reservation = {
        "successor_run_id": manifest["run_id"],
        "successor_epoch": epoch,
        "successor_manifest_digest": _digest(manifest),
        "successor_journal": str(resolved_successor_journal),
    }
    lock_path = resolved_predecessor_journal.with_suffix(
        f"{resolved_predecessor_journal.suffix}.lock"
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        predecessor_events = _load_events(resolved_predecessor_journal, predecessor)
        predecessor_status = _status(predecessor, predecessor_events)
        predecessor_states = _task_statuses(predecessor, predecessor_events)
        live_predecessor_tasks = sorted(
            (task for task, status in predecessor_states.items() if status in LIVE_TASK_STATUSES),
            key=_task_sort_key,
        )
        if live_predecessor_tasks:
            raise ControlError(
                "predecessor epoch still has live tasks: " + ", ".join(live_predecessor_tasks)
            )
        if predecessor_status["run_status"] not in {"complete", "failed"}:
            raise ControlError(
                "predecessor epoch must be terminal before a successor epoch is initialized"
            )
        reservations = [
            event for event in predecessor_events if event["type"] == "successor_epoch_reserved"
        ]
        if len(reservations) > 1:
            raise ControlError("predecessor journal has multiple successor reservations")
        if reservations:
            reservation_event = reservations[0]
            recorded = {field: reservation_event.get(field) for field in reservation}
            if recorded != reservation:
                raise ControlError("predecessor epoch is already reserved for another successor")
            if reservation_event is not predecessor_events[-1]:
                raise ControlError("predecessor journal advanced after its successor reservation")
        else:
            reservation_event = _append_event_under_lock(
                resolved_predecessor_journal,
                predecessor_events,
                "successor_epoch_reserved",
                reservation,
            )
    return {
        "predecessor_run_id": predecessor["run_id"],
        "predecessor_manifest_digest": predecessor_digest,
        "predecessor_journal_head": reservation_event["hash"],
        "predecessor_reservation_seq": reservation_event["seq"],
    }


def _task_statuses(manifest: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, str]:
    return {task: state["status"] for task, state in _task_states(manifest, events).items()}


def _task_states(
    manifest: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for task, definition in manifest["tasks"].items():
        status, merge_sha = _validate_task_initial(task, definition.get("initial", {}))
        state = {
            "status": "pending",
            "checks": {},
            "reviews": [],
            "review_packets": [],
            "pushed_sha": None,
        }
        if status == "merged":
            assert merge_sha is not None
            state.update({"status": "merged", "merge_sha": merge_sha})
        states[str(task)] = state
    rejection_limit = manifest.get("max_same_finding_rejections", 2)
    total_rejection_limit = manifest.get("max_review_rejections", 4)
    for event in events[1:]:
        if event["type"] == "recovery_classified":
            for recovered_task, outcome in event["outcomes"].items():
                if outcome == "redispatch":
                    states[recovered_task]["status"] = "redispatch"
                elif outcome in {"lost_local_only", "restart_required"}:
                    states[recovered_task]["status"] = "restart_required"
            continue
        task = event.get("task")
        if task not in states:
            continue
        if event["type"] == "task_started":
            states[task].update(
                {
                    "status": "active",
                    "base_sha": event["base_sha"],
                    "branch": event["branch"],
                    "dispatch_id": event["dispatch_id"],
                    "orca_task_id": event["orca_task_id"],
                    "terminal_handle": event["terminal_handle"],
                    "worktree_id": event["worktree_id"],
                    "worktree_path": event["worktree_path"],
                }
            )
        elif event["type"] == "task_checkpointed":
            states[task]["pushed_sha"] = event["sha"]
            states[task]["remote_ref"] = event["remote_ref"]
        elif event["type"] == "check_recorded":
            states[task]["checks"][event["name"]] = event
        elif event["type"] == "review_packet_issued":
            states[task]["review_packets"].append(event)
        elif event["type"] == "review_recorded":
            states[task]["reviews"].append(event)
            if event["verdict"] == "reject":
                counts: dict[str, int] = {}
                for review in states[task]["reviews"]:
                    if review["verdict"] != "reject":
                        continue
                    for finding in review["findings"]:
                        fingerprint = finding["fingerprint"]
                        counts[fingerprint] = counts.get(fingerprint, 0) + 1
                repeated = sorted(
                    fingerprint for fingerprint, count in counts.items() if count >= rejection_limit
                )
                if repeated:
                    states[task]["status"] = "needs_planner"
                    states[task]["repeated_findings"] = repeated
                    states[task]["gate_reason"] = {
                        "fingerprints": repeated,
                        "kind": "repeated_findings",
                    }
                else:
                    total_rejections = sum(
                        review["verdict"] == "reject" for review in states[task]["reviews"]
                    )
                    if total_rejections >= total_rejection_limit:
                        states[task]["status"] = "needs_planner"
                        states[task]["gate_reason"] = {
                            "count": total_rejections,
                            "kind": "total_review_rejections",
                        }
        elif event["type"] == "planner_gate_resolved":
            if event["action"] == "retry":
                states[task]["status"] = "active"
                states[task].pop("gate_reason", None)
                states[task].pop("repeated_findings", None)
            else:
                for _aborted_task, aborted_state in states.items():
                    if aborted_state["status"] == "merged":
                        continue
                    aborted_state["status"] = "abandoned"
                    aborted_state["aborted_by"] = task
                    aborted_state.pop("gate_reason", None)
                    aborted_state.pop("repeated_findings", None)
        elif event["type"] == "task_accepted":
            states[task]["status"] = "accepted"
            states[task]["accepted_sha"] = event["head_sha"]
            states[task]["accepted_repo"] = event["repo"]
            states[task]["base_ref"] = event["base_ref"]
            states[task]["evidence_digest"] = event["evidence_digest"]
            states[task]["pr_number"] = event["pr_number"]
            states[task]["accepted_changed_files"] = event["changed_files"]
            states[task]["accepted_pr_url"] = event["pr_url"]
        elif event["type"] == "merge_requested":
            states[task]["status"] = "merge_pending"
            states[task]["merge_request"] = event["merge_request"]
            states[task]["merge_request_digest"] = event["merge_request_digest"]
        elif event["type"] == "merge_reconciled_open":
            states[task]["status"] = "merge_pending"
            states[task]["merge_reconciliation"] = event["merge_state"]
        elif event["type"] == "task_merged":
            states[task]["status"] = "merged"
            states[task]["merge_sha"] = event["merge_sha"]
    return states


def _task_sort_key(task: str) -> tuple[int, int | str]:
    return (0, int(task)) if task.isdigit() else (1, task)


def _globs_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    left_literal = left.split("*", maxsplit=1)[0].rstrip("/")
    right_literal = right.split("*", maxsplit=1)[0].rstrip("/")
    if not left_literal or not right_literal:
        return True
    return (
        fnmatch.fnmatch(right_literal, left)
        or fnmatch.fnmatch(left_literal, right)
        or left_literal.startswith(f"{right_literal}/")
        or right_literal.startswith(f"{left_literal}/")
    )


def _ready(manifest: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = _task_statuses(manifest, events)
    active = sorted(
        (task for task, status in statuses.items() if status == "active"),
        key=_task_sort_key,
    )
    reserved = {task for task, status in statuses.items() if status in LIVE_TASK_STATUSES}
    capacity = max(0, manifest["max_concurrent"] - len(reserved))
    blocked_by_barrier: dict[str, str] = {}
    for barrier in manifest.get("barriers", []):
        gate = str(barrier["task"])
        if statuses.get(gate) == "merged":
            continue
        for blocked in barrier.get("blocks", []):
            blocked_by_barrier[str(blocked)] = gate
    blocked_by_live_ownership: dict[str, str] = {}
    pending_candidates = []
    recovery_candidates = []
    for task, definition in manifest["tasks"].items():
        task = str(task)
        task_status = statuses[task]
        if task_status not in {"pending", "redispatch", "restart_required"}:
            continue
        if task in blocked_by_barrier:
            continue
        dependencies = (str(dep) for dep in definition.get("depends_on", []))
        if not all(statuses[dependency] == "merged" for dependency in dependencies):
            continue
        for live_task in sorted(reserved, key=_task_sort_key):
            if live_task == task:
                continue
            live_definition = manifest["tasks"][live_task]
            if definition.get("repo") != live_definition.get("repo"):
                continue
            if any(
                _globs_overlap(candidate_glob, live_glob)
                for candidate_glob in definition.get("lane", [])
                for live_glob in live_definition.get("lane", [])
            ):
                blocked_by_live_ownership[task] = live_task
                break
        if task not in blocked_by_live_ownership:
            if task_status == "pending":
                pending_candidates.append(task)
            else:
                recovery_candidates.append(task)
    pending_candidates.sort(key=_task_sort_key)
    recovery_candidates.sort(key=_task_sort_key)
    result = {
        "active": active,
        "blocked_by_barrier": dict(
            sorted(
                blocked_by_barrier.items(),
                key=lambda item: _task_sort_key(item[0]),
            )
        ),
        "capacity": capacity,
        "ready": [*recovery_candidates, *pending_candidates[:capacity]],
        "seq": events[-1]["seq"],
    }
    if blocked_by_live_ownership:
        result["blocked_by_live_ownership"] = dict(
            sorted(blocked_by_live_ownership.items(), key=lambda item: _task_sort_key(item[0]))
        )
    return result


def _start_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    *,
    refresh_base: bool,
) -> dict[str, Any]:
    sources = manifest.get("sources")
    if isinstance(sources, dict) and sources.get("authority") == "recorded_replay":
        raise ControlError("recorded-replay manifests are non-dispatchable")
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    task = str(args.task)
    if task not in manifest["tasks"]:
        raise ControlError(f"unknown task: {task}")
    frontier = _ready(manifest, events)
    if task not in frontier["ready"]:
        gate = frontier["blocked_by_barrier"].get(task)
        if gate is not None:
            raise ControlError(f"task {task} is blocked by barrier task {gate}")
        status = _task_statuses(manifest, events)[task]
        raise ControlError(f"task {task} is not ready (status: {status})")
    if not args.worktree_path.is_absolute():
        raise ControlError("start --worktree-path must be absolute")
    if not args.base_repo.is_absolute():
        raise ControlError("start --base-repo must be absolute")
    if re.fullmatch(r"[0-9a-f]{40}", args.base_sha) is None:
        raise ControlError("start --base-sha must be a full lowercase 40-hex Git SHA")
    base_ref = args.base_ref
    if base_ref.startswith("refs/remotes/"):
        canonical_ref = base_ref
    elif not base_ref.startswith(("refs/", "-", "/")) and "/" in base_ref:
        canonical_ref = f"refs/remotes/{base_ref}"
    else:
        raise ControlError("start --base-ref must name a remote-tracking ref")
    try:
        _git_output(args.base_repo, "check-ref-format", canonical_ref)
    except ControlError as exc:
        raise ControlError("start --base-ref must name a valid remote-tracking ref") from exc
    tracking = canonical_ref.removeprefix("refs/remotes/")
    if "/" not in tracking:
        raise ControlError("start --base-ref must include a remote and branch")
    _, branch = tracking.split("/", maxsplit=1)
    manifest_base_ref = manifest.get("base_ref", "main")
    if branch != manifest_base_ref:
        raise ControlError(
            f"start base ref {canonical_ref} does not track manifest base {manifest_base_ref}"
        )
    task_repo = manifest["tasks"][task]["repo"]
    resolved_base = _resolve_recovery_remote_sha(
        args.base_repo,
        repo=task_repo,
        remote_ref=canonical_ref,
        refresh=refresh_base,
    )
    if resolved_base != args.base_sha:
        raise ControlError(
            f"start base ref {canonical_ref} resolves to {resolved_base}, not {args.base_sha}"
        )
    states = _task_states(manifest, events)
    required_ancestors: dict[str, str] = {}
    for dependency in manifest["tasks"][task].get("depends_on", []):
        dependency_state = states[dependency]
        if manifest["tasks"][dependency]["repo"] != task_repo:
            continue
        merge_sha = dependency_state.get("merge_sha")
        if not isinstance(merge_sha, str) or re.fullmatch(r"[0-9a-f]{40}", merge_sha) is None:
            raise ControlError(
                f"same-repository dependency {dependency} lacks a full merged commit SHA"
            )
        required_ancestors[f"dependency {dependency}"] = merge_sha
    source_main_sha = manifest.get("source_main_sha")
    epic_repo = str(manifest.get("epic", "")).partition("#")[0]
    if (
        task_repo.casefold() == epic_repo.casefold()
        and isinstance(source_main_sha, str)
        and re.fullmatch(r"[0-9a-f]{40}", source_main_sha)
    ):
        required_ancestors["manifest source_main_sha"] = source_main_sha
    for label, ancestor in required_ancestors.items():
        _verify_git_ancestor(
            args.base_repo,
            ancestor=ancestor,
            descendant=canonical_ref,
            label=label,
        )
    event = _append_event(
        journal,
        manifest,
        "task_started",
        {
            "task": task,
            "base_sha": args.base_sha,
            "base_ref": canonical_ref,
            "branch": args.branch,
            "dispatch_id": args.dispatch_id,
            "orca_task_id": args.orca_task_id,
            "terminal_handle": args.terminal_handle,
            "worktree_id": args.worktree_id,
            "worktree_path": str(args.worktree_path.resolve()),
        },
        args.expected_seq,
    )
    return {"seq": event["seq"], "status": "active", "task": task}


def _checkpoint_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    *,
    refresh_remote: bool,
) -> dict[str, Any]:
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    if states[task]["status"] != "active":
        raise ControlError(f"task {task} is not active (status: {states[task]['status']})")
    if not args.repo.is_absolute():
        raise ControlError("checkpoint --repo must be absolute")
    if re.fullmatch(r"[0-9a-f]{40}", args.sha) is None:
        raise ControlError("checkpoint --sha must be a full lowercase 40-hex Git SHA")
    remote_ref = args.remote_ref
    if remote_ref.startswith("refs/remotes/"):
        canonical_ref = remote_ref
    elif not remote_ref.startswith(("refs/", "-", "/")) and "/" in remote_ref:
        canonical_ref = f"refs/remotes/{remote_ref}"
    else:
        raise ControlError("checkpoint remote ref must name a remote-tracking ref")
    try:
        _git_output(args.repo, "check-ref-format", canonical_ref)
    except ControlError as exc:
        raise ControlError("checkpoint remote ref must name a valid remote-tracking ref") from exc
    if refresh_remote:
        remote_sha = _resolve_recovery_remote_sha(
            args.repo,
            repo=manifest["tasks"][task]["repo"],
            remote_ref=canonical_ref,
            refresh=True,
        )
    else:
        remote_sha = _git_output(
            args.repo,
            "rev-parse",
            "--verify",
            "--end-of-options",
            canonical_ref,
        )
    if remote_sha != args.sha:
        raise ControlError(f"remote ref {canonical_ref} resolves to {remote_sha}, not {args.sha}")
    event = _append_event(
        journal,
        manifest,
        "task_checkpointed",
        {"task": task, "sha": args.sha, "remote_ref": canonical_ref},
        args.expected_seq,
    )
    return {"seq": event["seq"], "sha": args.sha, "task": task}


def _check_definition(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [check for check in manifest.get("checks", []) if check.get("name") == name]
    if len(matches) != 1:
        raise ControlError(f"unknown or duplicate check: {name}")
    command = matches[0].get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(argument, str) for argument in command)
    ):
        raise ControlError(f"check {name} command must be a non-empty string array")
    return matches[0]


def _write_receipt(
    journal: Path,
    task: str,
    name: str,
    sha: str,
    receipt: dict[str, Any],
) -> Path:
    directory = journal.parent / f"{journal.stem}.receipts"
    directory.mkdir(parents=True, exist_ok=True)
    receipt_id = _digest({"name": name, "sha": sha, "task": task})[:24]
    path = directory / f"{receipt_id}.json"
    _write_json_atomic(path, receipt)
    return path


def _run_check(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    *,
    refresh_remote: bool,
) -> dict[str, Any]:
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    state = states[task]
    if state["status"] != "active" or not state.get("pushed_sha"):
        raise ControlError(f"task {task} needs a pushed checkpoint before checks run")
    if not args.repo.is_absolute():
        raise ControlError("run-check --repo must be absolute")
    definition = _check_definition(manifest, args.name)
    previous = state["checks"].get(args.name)
    if (
        previous is not None
        and previous.get("sha") == state["pushed_sha"]
        and previous.get("command") == definition["command"]
        and previous.get("exit_code") == 0
    ):
        return {
            "duplicate": True,
            "exit_code": 0,
            "output_digest": previous["output_digest"],
            "receipt_path": previous["receipt_path"],
            "seq": events[-1]["seq"],
            "sha": previous["sha"],
            "task": task,
        }
    head_sha = _git_output(args.repo, "rev-parse", "HEAD")
    if head_sha != state["pushed_sha"]:
        raise ControlError(
            f"check checkout SHA {head_sha} does not match pushed SHA {state['pushed_sha']}"
        )
    dirty = _git_output(args.repo, "status", "--porcelain")
    if dirty:
        raise ControlError("check checkout must be clean before the configured command runs")
    remote_ref = state.get("remote_ref")
    if not isinstance(remote_ref, str):
        raise ControlError(f"task {task} checkpoint is missing its remote ref")
    if refresh_remote:
        remote_sha = _resolve_recovery_remote_sha(
            args.repo,
            repo=manifest["tasks"][task]["repo"],
            remote_ref=remote_ref,
            refresh=True,
        )
    else:
        remote_sha = _git_output(
            args.repo,
            "rev-parse",
            "--verify",
            "--end-of-options",
            remote_ref,
        )
    if remote_sha != state["pushed_sha"]:
        raise ControlError(
            f"check remote ref {remote_ref} resolves to {remote_sha}, "
            f"not pushed SHA {state['pushed_sha']}"
        )
    try:
        completed = subprocess.run(
            definition["command"],
            cwd=args.repo,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ControlError(f"cannot start check {args.name}: {exc}") from exc
    post_head = _git_output(args.repo, "rev-parse", "HEAD")
    post_dirty = _git_output(args.repo, "status", "--porcelain")
    if post_head != head_sha or post_dirty:
        raise ControlError(
            "configured check mutated its checkout; receipts require the same clean pushed SHA "
            "before and after execution"
        )
    receipt = {
        "task": task,
        "name": args.name,
        "sha": head_sha,
        "command": definition["command"],
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    output_digest = _digest({"stdout": completed.stdout, "stderr": completed.stderr})
    receipt["output_digest"] = output_digest
    receipt_path = _write_receipt(journal, task, args.name, head_sha, receipt)
    event = _append_event(
        journal,
        manifest,
        "check_recorded",
        {
            "task": task,
            "name": args.name,
            "sha": head_sha,
            "command": definition["command"],
            "exit_code": completed.returncode,
            "output_digest": output_digest,
            "receipt_path": str(receipt_path),
        },
        args.expected_seq,
    )
    result = {
        "duplicate": False,
        "exit_code": completed.returncode,
        "output_digest": output_digest,
        "receipt_path": str(receipt_path),
        "seq": event["seq"],
        "sha": head_sha,
        "task": task,
    }
    if completed.returncode != 0:
        raise ControlError(
            f"check failed: {args.name} (exit {completed.returncode})",
            receipt=result,
        )
    return result


def _path_matches(path: str, pattern: str) -> bool:
    literal = pattern.split("*", maxsplit=1)[0].rstrip("/")
    return fnmatch.fnmatch(path, pattern) or bool(literal and path.startswith(f"{literal}/"))


REVIEW_PACKET_KEYS = {
    "schema_version",
    "kind",
    "run_id",
    "manifest_digest",
    "task",
    "repo",
    "pr_number",
    "pr_url",
    "head_sha",
    "base_ref",
    "scope",
    "reviewer",
    "reviewer_dispatch",
    "goal_path",
    "task_contract",
    "changed_files",
    "declarations",
    "local_receipts",
    "github_required_checks",
    "prior_review_count",
    "prior_reviews",
    "packet_digest",
}


def _packet_without_digest(packet: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in packet.items() if key != "packet_digest"}


def _review_packet(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    github_collector: GitHubCollector,
) -> dict[str, Any]:
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    state = states[task]
    definition = manifest["tasks"][task]
    if definition["risk"] != "novel":
        raise ControlError(f"task {task} is mechanical and must not receive agent review")
    if state["status"] != "active" or not state.get("pushed_sha"):
        raise ControlError(f"task {task} needs a pushed checkpoint before review")
    if isinstance(args.pr_number, bool) or args.pr_number < 1:
        raise ControlError("review packet PR number must be a positive integer")
    head_sha = state["pushed_sha"]
    required_checks = definition.get(
        "required_checks",
        [check["name"] for check in manifest.get("checks", [])],
    )
    local_receipts: list[dict[str, Any]] = []
    for name in required_checks:
        receipt = state["checks"].get(name)
        if (
            receipt is None
            or receipt.get("sha") != head_sha
            or receipt.get("exit_code") != 0
            or receipt.get("command") != _check_definition(manifest, name)["command"]
        ):
            raise ControlError(f"missing passing {name} receipt for head SHA {head_sha}")
        local_receipts.append(
            {
                "name": name,
                "sha": receipt["sha"],
                "command": receipt["command"],
                "exit_code": receipt["exit_code"],
                "output_digest": receipt["output_digest"],
                "receipt_path": receipt["receipt_path"],
            }
        )
    try:
        github_snapshot = github_collector(
            definition["repo"],
            args.pr_number,
            expected_head_sha=head_sha,
        )
        github_evidence.validate_pr_ci_snapshot(github_snapshot)
    except github_evidence.EvidenceError as exc:
        raise ControlError(f"GitHub review-packet evidence rejected: {exc}") from exc
    if (
        github_snapshot["repo"].casefold() != definition["repo"].casefold()
        or github_snapshot["number"] != args.pr_number
        or github_snapshot["head_sha"] != head_sha
        or github_snapshot["base_ref"] != manifest.get("base_ref", "main")
    ):
        raise ControlError("GitHub review-packet evidence does not match the task identity")
    declarations = _load_json(args.declarations) if args.declarations is not None else {}
    if not all(
        isinstance(path, str) and path and isinstance(reason, str) and reason.strip()
        for path, reason in declarations.items()
    ):
        raise ControlError(
            "review packet declarations must map non-empty paths to non-empty reasons"
        )
    changed_files = github_snapshot["changed_files"]
    if not set(declarations).issubset(changed_files):
        raise ControlError("review packet declarations must name changed files")
    scope = "full" if not state["reviews"] else "delta"
    all_prior_reviews = [
        {
            "head_sha": review["head_sha"],
            "scope": review["scope"],
            "verdict": review["verdict"],
            "findings": review["findings"],
        }
        for review in state["reviews"]
    ]
    prior_reviews = all_prior_reviews[-MAX_PACKET_PRIOR_REVIEWS:]
    packet = {
        "schema_version": 1,
        "kind": "epic_review_packet",
        "run_id": manifest["run_id"],
        "manifest_digest": _digest(manifest),
        "task": task,
        "repo": definition["repo"],
        "pr_number": args.pr_number,
        "pr_url": github_snapshot["pr_url"],
        "head_sha": head_sha,
        "base_ref": github_snapshot["base_ref"],
        "scope": scope,
        "reviewer": manifest["models"]["reviewer"],
        "reviewer_dispatch": {
            "dispatch_id": args.reviewer_dispatch_id,
            "terminal_handle": args.reviewer_terminal_handle,
            "worktree_id": args.reviewer_worktree_id,
        },
        "goal_path": _goal_paths(manifest)[task],
        "task_contract": _task_contract(manifest, task, state),
        "changed_files": changed_files,
        "declarations": declarations,
        "local_receipts": local_receipts,
        "github_required_checks": github_snapshot["required_checks"],
        "prior_review_count": len(all_prior_reviews),
        "prior_reviews": prior_reviews,
    }
    packet["packet_digest"] = _digest(packet)
    _write_json_atomic(args.output, packet)
    event = _append_event(
        journal,
        manifest,
        "review_packet_issued",
        {
            "task": task,
            "head_sha": head_sha,
            "packet_digest": packet["packet_digest"],
            "pr_number": args.pr_number,
            "pr_url": github_snapshot["pr_url"],
            "reviewer": packet["reviewer"],
            "reviewer_dispatch": packet["reviewer_dispatch"],
            "scope": scope,
        },
        args.expected_seq,
    )
    return {
        "head_sha": head_sha,
        "output": str(args.output),
        "packet_digest": packet["packet_digest"],
        "scope": scope,
        "seq": event["seq"],
        "task": task,
    }


def _validate_review_packet(
    packet: dict[str, Any],
    *,
    manifest: dict[str, Any],
    task: str,
    state: dict[str, Any],
) -> None:
    if set(packet) != REVIEW_PACKET_KEYS:
        raise ControlError("review packet has an invalid closed schema")
    all_prior_reviews = [
        {
            "head_sha": review["head_sha"],
            "scope": review["scope"],
            "verdict": review["verdict"],
            "findings": review["findings"],
        }
        for review in state["reviews"]
    ]
    if (
        packet["schema_version"] != 1
        or packet["kind"] != "epic_review_packet"
        or packet["run_id"] != manifest["run_id"]
        or packet["manifest_digest"] != _digest(manifest)
        or packet["task"] != task
        or packet["repo"].casefold() != manifest["tasks"][task]["repo"].casefold()
        or packet["head_sha"] != state["pushed_sha"]
        or packet["base_ref"] != manifest.get("base_ref", "main")
        or packet["reviewer"] != manifest["models"]["reviewer"]
        or packet["goal_path"] != _goal_paths(manifest)[task]
        or packet["task_contract"] != _task_contract(manifest, task, state)
        or packet["prior_review_count"] != len(all_prior_reviews)
        or packet["prior_reviews"] != all_prior_reviews[-MAX_PACKET_PRIOR_REVIEWS:]
    ):
        raise ControlError("review packet no longer matches the immutable task state")
    dispatch = packet["reviewer_dispatch"]
    if not isinstance(dispatch, dict) or set(dispatch) != {
        "dispatch_id",
        "terminal_handle",
        "worktree_id",
    }:
        raise ControlError("review packet reviewer_dispatch has an invalid closed schema")
    if not all(isinstance(value, str) and value.strip() for value in dispatch.values()):
        raise ControlError("review packet reviewer dispatch identifiers must be non-empty")
    if packet["scope"] not in {"full", "delta"}:
        raise ControlError("review packet scope must be full or delta")
    if packet["packet_digest"] != _digest(_packet_without_digest(packet)):
        raise ControlError("review packet digest does not match its content")
    matching_issues = [
        issued
        for issued in state["review_packets"]
        if issued["head_sha"] == state["pushed_sha"]
        and issued["packet_digest"] == packet["packet_digest"]
        and issued["reviewer_dispatch"] == packet["reviewer_dispatch"]
    ]
    if len(matching_issues) != 1:
        raise ControlError("review packet was not issued exactly once by this control journal")
    if any(review.get("packet_digest") == packet["packet_digest"] for review in state["reviews"]):
        raise ControlError("review packet has already been consumed")


def _record_review(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    state = states[task]
    if state["status"] != "active" or not state.get("pushed_sha"):
        raise ControlError(f"task {task} needs a pushed checkpoint before review")
    if manifest["tasks"][task].get("risk") != "novel":
        raise ControlError(f"task {task} is mechanical and must not receive agent review")
    packet = _load_json(args.packet)
    _validate_review_packet(packet, manifest=manifest, task=task, state=state)
    review = _load_json(args.review)
    expected_review_keys = {
        "task",
        "head_sha",
        "verdict",
        "scope",
        "reviewer",
        "findings",
        "packet_digest",
    }
    if set(review) != expected_review_keys:
        raise ControlError("review result has an invalid closed schema")
    if review["packet_digest"] != packet["packet_digest"]:
        raise ControlError("review result does not cite the supplied review packet")
    if str(review.get("task")) != task:
        raise ControlError(f"review task {review.get('task')!r} does not match task {task}")
    if review.get("head_sha") != state["pushed_sha"]:
        raise ControlError(
            f"review SHA {review.get('head_sha')!r} does not match pushed SHA "
            f"{state['pushed_sha']!r}"
        )
    if review.get("verdict") not in {"pass", "reject"}:
        raise ControlError("review verdict must be pass or reject")
    if review.get("scope") not in {"full", "delta"}:
        raise ControlError("review scope must be full or delta")
    if review["scope"] != packet["scope"]:
        raise ControlError("review scope does not match the supplied review packet")
    if review["scope"] == "delta" and not any(
        prior.get("scope") == "full" for prior in state["reviews"]
    ):
        raise ControlError("the first semantic review must have full scope")
    if any(
        prior.get("head_sha") == review["head_sha"] and prior.get("verdict") == "reject"
        for prior in state["reviews"]
    ):
        raise ControlError(
            f"task {task} already has a rejected review for unchanged SHA "
            f"{review['head_sha']}; checkpoint a fix first"
        )
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ControlError("review reviewer must be an object")
    expected_reviewer = manifest.get("models", {}).get("reviewer", {})
    if reviewer.get("family") != expected_reviewer.get("family") or reviewer.get(
        "model"
    ) != expected_reviewer.get("model"):
        raise ControlError(
            "reviewer identity does not match the manifest-pinned reviewer family and model"
        )
    worker_family = manifest.get("models", {}).get("worker", {}).get("family")
    if reviewer.get("family") == worker_family:
        raise ControlError("reviewer must use a different model family from the worker")
    findings = review.get("findings")
    if not isinstance(findings, list):
        raise ControlError("review findings must be an array")
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or not isinstance(finding.get("fingerprint"), str)
            or not finding["fingerprint"].strip()
            or not isinstance(finding.get("summary"), str)
            or not finding["summary"].strip()
        ):
            raise ControlError(
                "each review finding needs non-empty fingerprint and summary strings"
            )
    fingerprints = [finding["fingerprint"] for finding in findings]
    if len(fingerprints) != len(set(fingerprints)):
        raise ControlError("review findings contain duplicate fingerprints")
    if review["verdict"] == "pass" and findings:
        raise ControlError("a passing review cannot contain findings")
    if review["verdict"] == "reject" and not findings:
        raise ControlError("a rejected review must contain at least one finding")
    event = _append_event(
        journal,
        manifest,
        "review_recorded",
        {
            "task": task,
            "head_sha": review["head_sha"],
            "verdict": review["verdict"],
            "scope": review["scope"],
            "reviewer": reviewer,
            "findings": findings,
            "packet_digest": packet["packet_digest"],
            "reviewer_dispatch": packet["reviewer_dispatch"],
            "pr_number": packet["pr_number"],
            "pr_url": packet["pr_url"],
        },
        args.expected_seq,
    )
    updated = _task_states(manifest, [*events, event])[task]
    return {
        "seq": event["seq"],
        "status": updated["status"],
        "task": task,
        "verdict": review["verdict"],
    }


def _status(manifest: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    states = _task_states(manifest, events)
    frontier = _ready(manifest, events)
    planner_tasks = sorted(
        (task for task, state in states.items() if state["status"] == "needs_planner"),
        key=_task_sort_key,
    )
    redispatch = sorted(
        (task for task, state in states.items() if state["status"] == "redispatch"),
        key=_task_sort_key,
    )
    restart = sorted(
        (task for task, state in states.items() if state["status"] == "restart_required"),
        key=_task_sort_key,
    )
    accepted = sorted(
        (task for task, state in states.items() if state["status"] == "accepted"),
        key=_task_sort_key,
    )
    merge_pending = sorted(
        (task for task, state in states.items() if state["status"] == "merge_pending"),
        key=_task_sort_key,
    )
    abandoned = sorted(
        (task for task, state in states.items() if state["status"] == "abandoned"),
        key=_task_sort_key,
    )
    if abandoned:
        next_action = {"tasks": abandoned, "type": "failed"}
    elif merge_pending:
        next_action = {"tasks": merge_pending, "type": "reconcile_merge"}
    elif redispatch or restart:
        next_action = {
            "redispatch": redispatch,
            "restart": restart,
            "type": "recovery",
        }
    elif accepted:
        next_action = {"tasks": accepted, "type": "merge"}
    elif planner_tasks:
        next_action = {"tasks": planner_tasks, "type": "decision_gate"}
    elif frontier["ready"]:
        next_action = {"tasks": frontier["ready"], "type": "dispatch"}
    elif all(state["status"] == "merged" for state in states.values()):
        next_action = {"type": "complete"}
    else:
        next_action = {"type": "wait"}
    public_states = {
        task: {
            key: value
            for key, value in state.items()
            if key not in {"checks", "reviews", "review_packets"}
        }
        for task, state in states.items()
    }
    return {
        "next_action": next_action,
        "ready": frontier["ready"],
        "run_status": (
            "complete"
            if next_action["type"] == "complete"
            else "failed"
            if next_action["type"] == "failed"
            else "running"
        ),
        "seq": events[-1]["seq"],
        "tasks": public_states,
    }


def _resolve_gate(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    if states[task]["status"] != "needs_planner":
        raise ControlError(f"task {task} does not have an open planner gate")
    decision = _load_json(args.decision)
    if str(decision.get("task")) != task:
        raise ControlError(f"decision task does not match task {task}")
    if decision.get("action") not in {"retry", "abandon"}:
        raise ControlError("planner decision action must be retry or abandon")
    if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
        raise ControlError("planner decision needs a non-empty reason")
    actor = decision.get("actor")
    expected = manifest.get("models", {}).get("planner", {})
    if (
        not isinstance(actor, dict)
        or actor.get("family") != expected.get("family")
        or actor.get("model") != expected.get("model")
    ):
        raise ControlError("planner identity does not match the manifest-pinned planner")
    if decision["action"] == "abandon":
        blocking = sorted(
            (
                other_task
                for other_task, state in states.items()
                if other_task != task
                and state["status"]
                in {
                    "accepted",
                    "active",
                    "merge_pending",
                    "needs_planner",
                    "redispatch",
                    "restart_required",
                }
            ),
            key=_task_sort_key,
        )
        if blocking:
            rendered = ", ".join(
                f"{other_task}({states[other_task]['status']})" for other_task in blocking
            )
            raise ControlError(
                "cannot abandon the epoch while other tasks require quiescence: " + rendered
            )
    event = _append_event(
        journal,
        manifest,
        "planner_gate_resolved",
        {
            "task": task,
            "action": decision["action"],
            "reason": decision["reason"],
            "actor": actor,
        },
        args.expected_seq,
    )
    status = "active" if decision["action"] == "retry" else "abandoned"
    return {"seq": event["seq"], "status": status, "task": task}


def _merge_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    github_collector: GitHubCollector,
    github_merger: GitHubMerger,
    *,
    refresh_remote: bool,
) -> dict[str, Any]:
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    lock_path = journal.with_suffix(f"{journal.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        locked_events = _load_events(journal, manifest)
        return _merge_task_under_lock(
            manifest,
            locked_events,
            journal,
            args,
            github_collector,
            github_merger,
            refresh_remote=refresh_remote,
        )


def _merge_ref_context(
    checkout: Path,
    main_ref: str,
    base_ref: str,
    *,
    repo: str,
    refresh_remote: bool,
) -> tuple[str, str]:
    if main_ref.startswith("refs/remotes/"):
        canonical_ref = main_ref
    elif not main_ref.startswith(("refs/", "-", "/")) and "/" in main_ref:
        canonical_ref = f"refs/remotes/{main_ref}"
    else:
        raise ControlError("merge main ref must name a remote-tracking ref")
    try:
        _git_output(checkout, "check-ref-format", canonical_ref)
        _git_output(checkout, "rev-parse", "--git-dir")
        _git_output(
            checkout,
            "rev-parse",
            "--verify",
            "--end-of-options",
            canonical_ref,
        )
    except ControlError as exc:
        raise ControlError(
            f"cannot resolve merge main ref {canonical_ref} in {checkout}: {exc}"
        ) from exc
    if not canonical_ref.endswith(f"/{base_ref}"):
        raise ControlError(
            f"merge main ref {canonical_ref} does not track accepted base ref {base_ref}"
        )
    tracking_name = canonical_ref.removeprefix("refs/remotes/")
    remote = tracking_name[: -len(f"/{base_ref}")]
    if not remote:
        raise ControlError(f"merge main ref {canonical_ref} has no remote name")
    if refresh_remote:
        try:
            remote_url = _git_output(checkout, "remote", "get-url", remote)
        except ControlError as exc:
            raise ControlError(
                f"cannot resolve merge remote {remote} in {checkout}: {exc}"
            ) from exc
        actual_repo = _github_repo_from_remote_url(remote_url)
        if actual_repo is None or actual_repo.casefold() != repo.casefold():
            raise ControlError(
                f"merge remote {remote} URL does not identify manifest repository {repo}"
            )
    return canonical_ref, remote


def _verify_merge_reachable(
    checkout: Path,
    *,
    base_ref: str,
    canonical_ref: str,
    remote: str,
    merge_sha: str,
    refresh_remote: bool,
) -> None:
    if refresh_remote:
        try:
            _git_output(
                checkout,
                "fetch",
                "--no-tags",
                remote,
                f"+refs/heads/{base_ref}:{canonical_ref}",
            )
        except ControlError as exc:
            raise ControlError(
                f"cannot refresh merge main ref {canonical_ref} after GitHub merge: {exc}"
            ) from exc
    try:
        resolved_merge_sha = _git_output(
            checkout,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{merge_sha}^{{commit}}",
        )
    except ControlError as exc:
        raise ControlError(f"cannot resolve merge SHA {merge_sha} in {checkout}: {exc}") from exc
    if resolved_merge_sha != merge_sha:
        raise ControlError("merge SHA must be an exact commit object id")
    try:
        reachable = subprocess.run(
            ["git", "merge-base", "--is-ancestor", merge_sha, canonical_ref],
            cwd=checkout,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ControlError(f"cannot start git merge-base in {checkout}: {exc}") from exc
    if reachable.returncode == 1:
        raise ControlError(f"merge SHA {merge_sha} is not reachable from {canonical_ref}")
    if reachable.returncode != 0:
        detail = reachable.stderr.strip() or reachable.stdout.strip()
        raise ControlError(f"git merge-base --is-ancestor failed in {checkout}: {detail}")


def _validate_merge_preflight(
    snapshot: dict[str, Any],
    *,
    state: dict[str, Any],
    repo: str,
    pr_number: int,
) -> None:
    try:
        github_evidence.validate_pr_ci_snapshot(snapshot)
    except github_evidence.EvidenceError as exc:
        raise ControlError(f"GitHub merge preflight rejected: {exc}") from exc
    expected = {
        "repo": repo.casefold(),
        "number": pr_number,
        "head_sha": state["accepted_sha"],
        "base_ref": state["base_ref"],
        "pr_url": state["accepted_pr_url"].casefold(),
        "changed_files": state["accepted_changed_files"],
    }
    actual = {
        "repo": snapshot["repo"].casefold(),
        "number": snapshot["number"],
        "head_sha": snapshot["head_sha"],
        "base_ref": snapshot["base_ref"],
        "pr_url": snapshot["pr_url"].casefold(),
        "changed_files": snapshot["changed_files"],
    }
    if actual != expected:
        raise ControlError(
            "GitHub merge preflight no longer matches accepted PR evidence",
            actual=actual,
            expected=expected,
        )


def _merge_task_under_lock(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    github_collector: GitHubCollector,
    github_merger: GitHubMerger,
    *,
    refresh_remote: bool,
) -> dict[str, Any]:
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    state = states[task]
    if state["status"] != "accepted":
        raise ControlError(f"task {task} is not accepted")
    if isinstance(args.pr_number, bool) or args.pr_number < 1:
        raise ControlError("merge PR number must be a positive integer")
    if args.pr_number != state["pr_number"]:
        raise ControlError(
            f"merge PR number {args.pr_number} does not match accepted PR {state['pr_number']}"
        )
    definition = manifest["tasks"][task]
    repo = definition["repo"]
    if state["accepted_repo"].casefold() != repo.casefold():
        raise ControlError("accepted PR repo no longer matches the task manifest")
    head_sha = state["accepted_sha"]
    base_ref = state["base_ref"]
    canonical_ref, remote = _merge_ref_context(
        args.repo,
        args.main_ref,
        base_ref,
        repo=repo,
        refresh_remote=refresh_remote,
    )
    try:
        preflight = github_collector(
            repo,
            args.pr_number,
            expected_head_sha=head_sha,
        )
    except github_evidence.EvidenceError as exc:
        raise ControlError(f"GitHub merge preflight rejected: {exc}") from exc
    _validate_merge_preflight(
        preflight,
        state=state,
        repo=repo,
        pr_number=args.pr_number,
    )
    merge_request = {
        "repo": repo,
        "number": args.pr_number,
        "expected_head_sha": head_sha,
        "merge_method": args.merge_method,
        "main_ref": canonical_ref,
        "preflight_digest": _digest(preflight),
        "preflight_required_checks": preflight["required_checks"],
    }
    intent = _append_event_under_lock(
        journal,
        events,
        "merge_requested",
        {
            "task": task,
            "head_sha": head_sha,
            "pr_number": args.pr_number,
            "repo": repo,
            "merge_request": merge_request,
            "merge_request_digest": _digest(merge_request),
        },
    )
    events_after_intent = [*events, intent]
    try:
        merge_result = github_merger(
            repo,
            args.pr_number,
            expected_head_sha=head_sha,
            merge_method=args.merge_method,
        )
    except github_evidence.EvidenceError as exc:
        raise ControlError(
            "GitHub PR merge outcome is uncertain; run reconcile-merge "
            f"for intent seq {intent['seq']}: {exc}"
        ) from exc
    expected_result_keys = {
        "schema_version",
        "kind",
        "source",
        "repo",
        "number",
        "expected_head_sha",
        "merge_method",
        "merged",
        "merge_sha",
        "message",
    }
    if not isinstance(merge_result, dict) or set(merge_result) != expected_result_keys:
        raise ControlError(
            "GitHub PR merge outcome is uncertain; run reconcile-merge because "
            "the result has an invalid closed schema"
        )
    if (
        merge_result["schema_version"] != 1
        or merge_result["kind"] != "github_pr_merge_result"
        or merge_result["source"] != "github"
        or not isinstance(merge_result["repo"], str)
        or merge_result["repo"].casefold() != repo.casefold()
        or merge_result["number"] != args.pr_number
        or merge_result["expected_head_sha"] != head_sha
        or merge_result["merge_method"] != args.merge_method
        or merge_result["merged"] is not True
        or not isinstance(merge_result["message"], str)
        or not merge_result["message"].strip()
    ):
        raise ControlError(
            "GitHub PR merge outcome is uncertain; run reconcile-merge because "
            "the result does not match the pinned request"
        )
    merge_sha = merge_result["merge_sha"]
    if (
        not isinstance(merge_sha, str)
        or len(merge_sha) != 40
        or any(character not in "0123456789abcdef" for character in merge_sha)
    ):
        raise ControlError(
            "GitHub PR merge outcome is uncertain; run reconcile-merge because "
            "the result has an invalid merge SHA"
        )
    try:
        _verify_merge_reachable(
            args.repo,
            base_ref=base_ref,
            canonical_ref=canonical_ref,
            remote=remote,
            merge_sha=merge_sha,
            refresh_remote=refresh_remote,
        )
    except ControlError as exc:
        raise ControlError(
            "GitHub PR merged but local proof is incomplete; run reconcile-merge "
            f"for intent seq {intent['seq']}: {exc}"
        ) from exc
    event = _append_event_under_lock(
        journal,
        events_after_intent,
        "task_merged",
        {
            "task": task,
            "head_sha": head_sha,
            "main_ref": canonical_ref,
            "merge_method": args.merge_method,
            "merge_request": merge_request,
            "merge_request_digest": _digest(merge_request),
            "merge_result": merge_result,
            "merge_result_digest": _digest(merge_result),
            "merge_sha": merge_sha,
            "pr_number": args.pr_number,
            "repo": repo,
        },
    )
    frontier = _ready(manifest, [*events_after_intent, event])
    return {
        "head_sha": head_sha,
        "main_ref": canonical_ref,
        "merge_method": args.merge_method,
        "merge_sha": merge_sha,
        "pr_number": args.pr_number,
        "ready": frontier["ready"],
        "seq": event["seq"],
        "status": "merged",
        "task": task,
    }


def _reconcile_merge(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    merge_state_collector: GitHubMergeStateCollector,
    *,
    refresh_remote: bool,
) -> dict[str, Any]:
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    lock_path = journal.with_suffix(f"{journal.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        locked_events = _load_events(journal, manifest)
        if locked_events[-1]["seq"] != args.expected_seq:
            raise ControlError(
                "journal advanced: expected seq "
                f"{args.expected_seq}, found {locked_events[-1]['seq']}"
            )
        task = str(args.task)
        states = _task_states(manifest, locked_events)
        if task not in states:
            raise ControlError(f"unknown task: {task}")
        state = states[task]
        if state["status"] != "merge_pending":
            raise ControlError(f"task {task} has no merge pending reconciliation")
        request = state["merge_request"]
        repo = manifest["tasks"][task]["repo"]
        try:
            snapshot = merge_state_collector(
                repo,
                request["number"],
                expected_head_sha=request["expected_head_sha"],
            )
            github_evidence.validate_pr_merge_state(snapshot)
        except github_evidence.EvidenceError as exc:
            raise ControlError(f"GitHub merge reconciliation failed: {exc}") from exc
        if (
            snapshot["repo"].casefold() != repo.casefold()
            or snapshot["number"] != request["number"]
            or snapshot["head_sha"] != request["expected_head_sha"]
            or snapshot["base_ref"] != state["base_ref"]
        ):
            raise ControlError(
                "GitHub merge reconciliation identity/base does not match the durable intent"
            )
        if snapshot["merged"] is not True:
            if snapshot["state"] != "open":
                raise ControlError(
                    "GitHub PR closed without merging; the durable intent remains pending. "
                    "Repair or merge the pinned PR, then rerun reconcile-merge"
                )
            event = _append_event_under_lock(
                journal,
                locked_events,
                "merge_reconciled_open",
                {
                    "task": task,
                    "merge_state": snapshot,
                    "merge_state_digest": _digest(snapshot),
                },
            )
            return {
                "pr_number": request["number"],
                "seq": event["seq"],
                "status": "merge_pending",
                "task": task,
            }
        merge_sha = snapshot["merge_sha"]
        canonical_ref, remote = _merge_ref_context(
            args.repo,
            args.main_ref,
            state["base_ref"],
            repo=repo,
            refresh_remote=refresh_remote,
        )
        _verify_merge_reachable(
            args.repo,
            base_ref=state["base_ref"],
            canonical_ref=canonical_ref,
            remote=remote,
            merge_sha=merge_sha,
            refresh_remote=refresh_remote,
        )
        event = _append_event_under_lock(
            journal,
            locked_events,
            "task_merged",
            {
                "task": task,
                "head_sha": request["expected_head_sha"],
                "main_ref": canonical_ref,
                "merge_method": request["merge_method"],
                "merge_request": request,
                "merge_request_digest": state["merge_request_digest"],
                "merge_state": snapshot,
                "merge_state_digest": _digest(snapshot),
                "merge_sha": merge_sha,
                "pr_number": request["number"],
                "reconciled": True,
                "repo": repo,
            },
        )
        frontier = _ready(manifest, [*locked_events, event])
        return {
            "head_sha": request["expected_head_sha"],
            "main_ref": canonical_ref,
            "merge_sha": merge_sha,
            "pr_number": request["number"],
            "ready": frontier["ready"],
            "reconciled": True,
            "seq": event["seq"],
            "status": "merged",
            "task": task,
        }


def _recover(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    *,
    refresh_remotes: bool,
) -> dict[str, Any]:
    states = _task_states(manifest, events)
    active = {
        task
        for task, state in states.items()
        if state["status"] in {"active", "redispatch", "restart_required"}
    }
    repo_paths = _load_json(args.repos)
    expected_repos = {manifest["tasks"][task]["repo"] for task in active}
    if set(repo_paths) != expected_repos:
        missing = sorted(expected_repos - set(repo_paths))
        unexpected = sorted(set(repo_paths) - expected_repos)
        raise ControlError(
            "recovery repo map must cover exactly the live task repositories "
            f"(missing={missing}, unexpected={unexpected})"
        )
    checkouts: dict[str, Path] = {}
    for repo, raw_path in repo_paths.items():
        if not isinstance(raw_path, str) or not raw_path:
            raise ControlError(f"recovery repo map path for {repo} must be non-empty")
        checkout = Path(raw_path)
        if not checkout.is_absolute():
            raise ControlError(f"recovery repo map path for {repo} must be absolute")
        _git_output(checkout, "rev-parse", "--git-dir")
        checkouts[repo] = checkout
    outcomes: dict[str, str] = {}
    observations: dict[str, dict[str, Any]] = {}
    for task in sorted(active, key=_task_sort_key):
        state = states[task]
        repo = manifest["tasks"][task]["repo"]
        checkout = checkouts[repo]
        pushed_sha = state.get("pushed_sha")
        remote_ref = state.get("remote_ref")
        remote_sha: str | None = None
        remote_error: str | None = None
        if pushed_sha:
            if not isinstance(remote_ref, str):
                raise ControlError(f"task {task} has a pushed SHA without a recorded remote ref")
            remote, branch = _recovery_remote_context(
                checkout,
                repo=repo,
                remote_ref=remote_ref,
            )
            try:
                remote_sha = _resolve_validated_remote_sha(
                    checkout,
                    remote_ref=remote_ref,
                    remote=remote,
                    branch=branch,
                    refresh=refresh_remotes,
                )
            except ControlError as exc:
                remote_error = str(exc)
        worktree = Path(state["worktree_path"])
        worktree_exists = worktree.exists()
        observation: dict[str, Any] = {
            "worktree_exists": worktree_exists,
            "remote_ref": remote_ref,
            "remote_sha": remote_sha,
        }
        if remote_error is not None:
            observation["remote_error"] = remote_error
        if worktree_exists:
            try:
                local_head = _git_output(worktree, "rev-parse", "HEAD")
                dirty = bool(_git_output(worktree, "status", "--porcelain"))
            except ControlError:
                local_head = None
                dirty = True
            observation.update({"local_head": local_head, "dirty": dirty})
            if not dirty and pushed_sha and local_head == pushed_sha and remote_sha == pushed_sha:
                outcomes[task] = "healthy"
            else:
                outcomes[task] = "restart_required"
            observations[task] = observation
            continue
        if remote_error is not None:
            outcomes[task] = "restart_required"
        elif pushed_sha and remote_sha == pushed_sha:
            outcomes[task] = "redispatch"
        else:
            outcomes[task] = "lost_local_only"
        observations[task] = observation
    event = _append_event(
        journal,
        manifest,
        "recovery_classified",
        {"observations": observations, "outcomes": outcomes},
        args.expected_seq,
    )
    result = {
        "healthy": [task for task, outcome in outcomes.items() if outcome == "healthy"],
        "lost_local_only": [
            task for task, outcome in outcomes.items() if outcome == "lost_local_only"
        ],
        "redispatch": [task for task, outcome in outcomes.items() if outcome == "redispatch"],
        "seq": event["seq"],
    }
    restart_required = [task for task, outcome in outcomes.items() if outcome == "restart_required"]
    if restart_required:
        result["restart_required"] = restart_required
    return result


def _github_repo_from_remote_url(url: str) -> str | None:
    normalized = url.strip().removesuffix("/").removesuffix(".git")
    for prefix in (
        "https://github.com/",
        "http://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    ):
        if normalized.casefold().startswith(prefix.casefold()):
            candidate = normalized[len(prefix) :]
            return candidate if candidate.count("/") == 1 else None
    return None


def _recovery_remote_context(
    checkout: Path,
    *,
    repo: str,
    remote_ref: str,
) -> tuple[str, str]:
    prefix = "refs/remotes/"
    if not remote_ref.startswith(prefix):
        raise ControlError(f"recovery remote ref must start with {prefix}: {remote_ref}")
    tracking = remote_ref.removeprefix(prefix)
    if "/" not in tracking:
        raise ControlError(f"recovery remote ref has no branch: {remote_ref}")
    remote, branch = tracking.split("/", maxsplit=1)
    remote_url = _git_output(checkout, "remote", "get-url", remote)
    actual_repo = _github_repo_from_remote_url(remote_url)
    if actual_repo is None or actual_repo.casefold() != repo.casefold():
        raise ControlError(
            f"recovery remote {remote} URL does not identify manifest repository {repo}"
        )
    return remote, branch


def _resolve_validated_remote_sha(
    checkout: Path,
    *,
    remote_ref: str,
    remote: str,
    branch: str,
    refresh: bool,
) -> str:
    if refresh:
        _git_output(
            checkout,
            "fetch",
            "--no-tags",
            remote,
            f"+refs/heads/{branch}:{remote_ref}",
        )
    return _git_output(
        checkout,
        "rev-parse",
        "--verify",
        "--end-of-options",
        remote_ref,
    )


def _resolve_recovery_remote_sha(
    checkout: Path,
    *,
    repo: str,
    remote_ref: str,
    refresh: bool,
) -> str:
    remote, branch = _recovery_remote_context(
        checkout,
        repo=repo,
        remote_ref=remote_ref,
    )
    return _resolve_validated_remote_sha(
        checkout,
        remote_ref=remote_ref,
        remote=remote,
        branch=branch,
        refresh=refresh,
    )


def _find_task_envelope(cwd: Path) -> tuple[Path, dict[str, Any]] | None:
    current = cwd.resolve()
    for directory in (current, *current.parents):
        path = directory / ".orchestration" / "task-envelope.json"
        if path.is_file():
            return directory, _load_json(path)
    return None


def _envelope_control_paths(root: Path, envelope: dict[str, Any]) -> tuple[Path, Path]:
    if envelope.get("schema_version") != 1:
        raise ControlError("task envelope schema_version must be 1")

    def resolve_path(name: str) -> Path:
        raw = envelope.get(name)
        if not isinstance(raw, str) or not raw:
            raise ControlError(f"task envelope needs a {name} path")
        path = Path(raw)
        return (path if path.is_absolute() else root / path).resolve()

    manifest = resolve_path("manifest")
    journal = resolve_path("journal")
    return manifest, journal


def _envelope_paths(root: Path, envelope: dict[str, Any]) -> tuple[Path, Path, Path, str]:
    if envelope.get("role") != "worker":
        raise ControlError("worker hook needs a worker task envelope")
    task = envelope.get("task")
    if not isinstance(task, str) or not task:
        raise ControlError("task envelope needs a task string")
    manifest, journal = _envelope_control_paths(root, envelope)
    raw_worktree = envelope.get("worktree_path")
    if not isinstance(raw_worktree, str) or not raw_worktree:
        raise ControlError("task envelope needs a worktree_path path")
    worktree_path = Path(raw_worktree)
    worktree = (worktree_path if worktree_path.is_absolute() else root / worktree_path).resolve()
    return manifest, journal, worktree, task


def _read_hook_input() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ControlError(f"hook input is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ControlError("hook input must be a JSON object")
    return payload


def _emit_hook(value: dict[str, Any]) -> None:
    sys.stdout.write(_canonical_json(value) + "\n")


def _hook_pre_tool_use(
    payload: dict[str, Any],
    root: Path,
    envelope: dict[str, Any],
) -> None:
    manifest_path, journal_path, worktree, task = _envelope_paths(root, envelope)
    manifest = _load_manifest(manifest_path)
    events = _load_events(journal_path, manifest)
    states = _task_states(manifest, events)
    state = states.get(task)
    tool_name = payload.get("tool_name")
    if tool_name not in {"Agent", "Edit", "Write"}:
        return
    if state is None:
        _emit_hook(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"orchestration guard denied {tool_name} because task {task} "
                        "is absent from durable state"
                    ),
                }
            }
        )
        return
    if tool_name == "Agent":
        _emit_hook(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "orchestration guard denied an untracked Agent subagent "
                        f"while task {task} is {state['status']}"
                    ),
                }
            }
        )
        return
    if state["status"] == "accepted":
        _emit_hook(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"orchestration guard denied edits because task {task} "
                        "accepted head is immutable"
                    ),
                }
            }
        )
        return
    if state["status"] == "needs_planner":
        _emit_hook(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"orchestration guard denied edits because task {task} planner gate is open"
                    ),
                }
            }
        )
        return
    if state["status"] != "active":
        _emit_hook(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"orchestration guard denied edits because task {task} "
                        f"is frozen in {state['status']}"
                    ),
                }
            }
        )
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        raise ControlError("PreToolUse tool_input must be an object")
    raw_path = tool_input.get("file_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ControlError("PreToolUse Edit/Write needs tool_input.file_path")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = Path(str(payload.get("cwd", worktree))) / candidate
    try:
        relative = candidate.resolve().relative_to(worktree).as_posix()
    except ValueError:
        reason = f"orchestration guard denied a write outside the task worktree: {raw_path}"
    else:
        definition = manifest["tasks"][task]
        forbidden = [
            *manifest.get("protected_paths", []),
            *manifest.get("no_go_paths", []),
            *definition.get("forbidden_paths", []),
        ]
        matched = next(
            (pattern for pattern in forbidden if _path_matches(relative, pattern)),
            None,
        )
        if matched is not None:
            reason = (
                f"orchestration guard denied hard-forbidden path {relative} (matched {matched})"
            )
        else:
            owner = next(
                (
                    other_task
                    for other_task, other_state in states.items()
                    if other_task != task
                    and other_state["status"]
                    in {
                        "active",
                        "accepted",
                        "merge_pending",
                        "needs_planner",
                        "redispatch",
                        "restart_required",
                    }
                    and manifest["tasks"][task].get("repo")
                    == manifest["tasks"][other_task].get("repo")
                    and any(
                        _path_matches(relative, pattern)
                        for pattern in manifest["tasks"][other_task].get("lane", [])
                    )
                ),
                None,
            )
            if owner is None:
                return
            reason = f"orchestration guard denied {relative} owned by live task {owner}"
    _emit_hook(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def _git_output(worktree: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=worktree,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ControlError(f"cannot start git {' '.join(args)} in {worktree}: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ControlError(f"git {' '.join(args)} failed in {worktree}: {detail}")
    return completed.stdout.strip()


def _verify_git_ancestor(
    checkout: Path,
    *,
    ancestor: str,
    descendant: str,
    label: str,
) -> None:
    try:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=checkout,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ControlError(f"cannot start git merge-base in {checkout}: {exc}") from exc
    if completed.returncode == 0:
        return
    if completed.returncode == 1:
        raise ControlError(f"{label} {ancestor} is not an ancestor of {descendant}")
    detail = completed.stderr.strip() or completed.stdout.strip()
    raise ControlError(
        f"cannot verify {label} {ancestor} against {descendant} in {checkout}: {detail}"
    )


def _hook_stop(
    payload: dict[str, Any],
    root: Path,
    envelope: dict[str, Any],
) -> None:
    if payload.get("stop_hook_active") is True:
        return
    manifest_path, journal_path, worktree, task = _envelope_paths(root, envelope)
    manifest = _load_manifest(manifest_path)
    events = _load_events(journal_path, manifest)
    state = _task_states(manifest, events).get(task)
    if state is None or state["status"] not in {"active", "needs_planner"}:
        return
    dirty = _git_output(worktree, "status", "--porcelain")
    if dirty:
        reason = (
            f"task {task} has uncommitted work; commit, push, and record a "
            "checkpoint before stopping"
        )
        _emit_hook({"decision": "block", "reason": reason})
        return
    head = _git_output(worktree, "rev-parse", "HEAD")
    try:
        upstream = _git_output(worktree, "rev-parse", "@{u}")
    except ControlError:
        upstream = ""
    if upstream != head:
        reason = (
            f"task {task} HEAD {head} is not pushed to its upstream; push and "
            "record a checkpoint before stopping"
        )
        _emit_hook({"decision": "block", "reason": reason})
        return
    if state.get("pushed_sha") != head:
        reason = (
            f"task {task} HEAD {head} lacks a matching durable checkpoint; "
            "record it before stopping"
        )
        _emit_hook({"decision": "block", "reason": reason})


def _task_contract(
    manifest: dict[str, Any],
    task: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    definition = manifest["tasks"][task]
    contract = {
        "task": task,
        "repo": definition["repo"],
        "risk": definition["risk"],
        "acceptance_criteria": definition.get("acceptance_criteria", []),
        "depends_on": definition.get("depends_on", []),
        "done_artifacts": definition.get("done_artifacts", []),
        "lane": definition["lane"],
        "forbidden_paths": definition.get("forbidden_paths", []),
        "protected_paths": manifest.get("protected_paths", []),
        "no_go_paths": manifest.get("no_go_paths", []),
        "required_checks": definition.get(
            "required_checks",
            [check["name"] for check in manifest.get("checks", [])],
        ),
        "base_ref": manifest.get("base_ref", "main"),
        "base_sha": state.get("base_sha"),
        "branch": state.get("branch"),
        "pushed_sha": state.get("pushed_sha"),
    }
    for field in (
        "source",
        "consumes_contracts",
        "produces_contracts",
        "receives_after",
        "transfers_after",
    ):
        if field in definition:
            contract[field] = definition[field]
    return json.loads(_canonical_json(contract))


def _worker_next_action(
    manifest: dict[str, Any],
    task: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    if state["status"] == "needs_planner":
        return {"type": "planner_gate"}
    if state["status"] != "active":
        return {
            "reason": f"task is frozen in {state['status']}",
            "type": "stop",
        }
    pushed_sha = state.get("pushed_sha")
    if not pushed_sha:
        return {"type": "checkpoint"}
    definition = manifest["tasks"][task]
    required_checks = definition.get(
        "required_checks",
        [check["name"] for check in manifest.get("checks", [])],
    )
    missing_checks = [
        name
        for name in required_checks
        if state["checks"].get(name, {}).get("sha") != pushed_sha
        or state["checks"].get(name, {}).get("exit_code") != 0
    ]
    if missing_checks:
        return {"checks": missing_checks, "type": "run_checks"}
    if definition["risk"] == "novel":
        current_reviews = [
            review for review in state["reviews"] if review.get("head_sha") == pushed_sha
        ]
        if not current_reviews:
            scope = "full" if not state["reviews"] else "delta"
            return {"scope": scope, "type": "review"}
        if current_reviews[-1]["verdict"] != "pass":
            return {
                "findings": current_reviews[-1]["findings"],
                "type": "fix_review_findings",
            }
    return {"type": "accept_pr"}


def _hook_session_start(
    root: Path,
    envelope: dict[str, Any],
) -> None:
    manifest_path, journal_path, _, task = _envelope_paths(root, envelope)
    manifest = _load_manifest(manifest_path)
    events = _load_events(journal_path, manifest)
    state = _task_states(manifest, events).get(task)
    if state is None:
        return
    goal_path = _goal_paths(manifest)[task]
    contract = _task_contract(manifest, task, state)
    next_action = _worker_next_action(manifest, task, state)
    context = (
        f"Durable orchestration task {task}: status={state['status']}; "
        f"journal_seq={events[-1]['seq']}; "
        f"pushed_sha={state.get('pushed_sha') or 'none'}; "
        f"goal_path={_canonical_json(goal_path)}; "
        f"task_contract={_canonical_json(contract)}; "
        f"next_action={_canonical_json(next_action)}. "
        "Work only this immutable leaf contract."
    )
    _emit_hook(
        {
            "hookSpecificOutput": {
                "additionalContext": context,
                "hookEventName": "SessionStart",
            }
        }
    )


def _coordinator_hook_state(
    root: Path, envelope: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_path, journal_path = _envelope_control_paths(root, envelope)
    manifest = _load_manifest(manifest_path)
    events = _load_events(journal_path, manifest)
    return events, _status(manifest, events)


def _hook_coordinator_pre_tool_use(
    payload: dict[str, Any],
) -> None:
    if payload.get("tool_name") != "Agent":
        return
    _emit_hook(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "orchestration guard denied an untracked Agent subagent "
                    "while the coordinator envelope is active"
                ),
            }
        }
    )


def _hook_coordinator_stop(
    payload: dict[str, Any],
    root: Path,
    envelope: dict[str, Any],
) -> None:
    if payload.get("stop_hook_active") is True:
        return
    _, status = _coordinator_hook_state(root, envelope)
    next_action = status["next_action"]
    if next_action["type"] in {"complete", "failed"}:
        return
    rendered = _canonical_json(next_action)
    _emit_hook(
        {
            "decision": "block",
            "reason": f"coordinator has durable next action {rendered}",
        }
    )


def _hook_coordinator_session_start(
    root: Path,
    envelope: dict[str, Any],
) -> None:
    events, status = _coordinator_hook_state(root, envelope)
    context = (
        f"Durable orchestration coordinator: journal_seq={events[-1]['seq']}; "
        f"next_action={_canonical_json(status['next_action'])}. "
        "Drive the recorded action instead of polling or reconstructing state."
    )
    _emit_hook(
        {
            "hookSpecificOutput": {
                "additionalContext": context,
                "hookEventName": "SessionStart",
            }
        }
    )


def _run_hook(mode: str) -> int:
    payload = _read_hook_input()
    cwd_raw = payload.get("cwd")
    if not isinstance(cwd_raw, str) or not cwd_raw:
        raise ControlError("hook input needs cwd")
    found = _find_task_envelope(Path(cwd_raw))
    if found is None:
        return 0
    root, envelope = found
    role = envelope.get("role")
    if role == "coordinator":
        if mode == "pre-tool-use":
            _hook_coordinator_pre_tool_use(payload)
        elif mode == "stop":
            _hook_coordinator_stop(payload, root, envelope)
        else:
            _hook_coordinator_session_start(root, envelope)
        return 0
    if role != "worker":
        raise ControlError("task envelope role must be worker or coordinator")
    if mode == "pre-tool-use":
        _hook_pre_tool_use(payload, root, envelope)
    elif mode == "stop":
        _hook_stop(payload, root, envelope)
    else:
        _hook_session_start(root, envelope)
    return 0


def _write_task_envelope(
    manifest_path: Path,
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    if args.role == "coordinator":
        if args.task is not None:
            raise ControlError("coordinator envelope does not accept a task")
        envelope = {
            "journal": str(journal.resolve()),
            "manifest": str(manifest_path.resolve()),
            "role": "coordinator",
            "schema_version": 1,
            "seq": events[-1]["seq"],
        }
        _write_json_atomic(args.output, envelope)
        return {
            "output": str(args.output),
            "role": "coordinator",
            "seq": events[-1]["seq"],
        }
    if args.task is None:
        raise ControlError("worker envelope requires a task")
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    state = states[task]
    if state["status"] not in {
        "active",
        "needs_planner",
        "redispatch",
        "restart_required",
    }:
        raise ControlError(f"task {task} has no live work envelope (status: {state['status']})")
    envelope = {
        "journal": str(journal.resolve()),
        "manifest": str(manifest_path.resolve()),
        "dispatch_id": state["dispatch_id"],
        "goal_path": _goal_paths(manifest)[task],
        "orca_task_id": state["orca_task_id"],
        "role": "worker",
        "schema_version": 1,
        "seq": events[-1]["seq"],
        "task": task,
        "task_contract": _task_contract(manifest, task, state),
        "terminal_handle": state["terminal_handle"],
        "worktree_id": state["worktree_id"],
        "worktree_path": state["worktree_path"],
    }
    _write_json_atomic(args.output, envelope)
    return {"output": str(args.output), "seq": events[-1]["seq"], "task": task}


def _accept_task(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    journal: Path,
    args: argparse.Namespace,
    github_collector: GitHubCollector,
) -> dict[str, Any]:
    if events[-1]["seq"] != args.expected_seq:
        raise ControlError(
            f"journal advanced: expected seq {args.expected_seq}, found {events[-1]['seq']}"
        )
    task = str(args.task)
    states = _task_states(manifest, events)
    if task not in states:
        raise ControlError(f"unknown task: {task}")
    state = states[task]
    if state["status"] != "active":
        raise ControlError(f"task {task} is not active")
    if isinstance(args.pr_number, bool) or args.pr_number < 1:
        raise ControlError("accept PR number must be a positive integer")
    head_sha = state.get("pushed_sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise ControlError(f"task {task} needs a pushed checkpoint before acceptance")
    definition = manifest["tasks"][task]
    repo = definition["repo"]
    base_ref = manifest.get("base_ref", "main")
    try:
        snapshot = github_collector(
            repo,
            args.pr_number,
            expected_head_sha=head_sha,
        )
        github_evidence.validate_pr_ci_snapshot(snapshot)
    except github_evidence.EvidenceError as exc:
        raise ControlError(f"GitHub PR evidence rejected: {exc}") from exc
    if snapshot.get("repo", "").casefold() != repo.casefold():
        raise ControlError(
            f"GitHub PR repo {snapshot.get('repo')!r} does not match task repo {repo!r}"
        )
    if snapshot.get("number") != args.pr_number:
        raise ControlError(
            f"GitHub PR number {snapshot.get('number')!r} does not match requested "
            f"PR {args.pr_number}"
        )
    if snapshot.get("head_sha") != head_sha:
        raise ControlError(
            f"GitHub PR head SHA {snapshot.get('head_sha')!r} does not match "
            f"pushed SHA {head_sha!r}"
        )
    if snapshot.get("base_ref") != base_ref:
        raise ControlError(
            f"GitHub PR base ref {snapshot.get('base_ref')!r} does not match "
            f"manifest base ref {base_ref!r}"
        )
    if manifest.get("require_ci", True):
        ci = snapshot.get("ci")
        if (
            not isinstance(ci, dict)
            or ci.get("head_sha") != head_sha
            or ci.get("state") != "success"
        ):
            raise ControlError(f"CI is not successful for head SHA {head_sha}")
    required_checks = definition.get(
        "required_checks", [check["name"] for check in manifest.get("checks", [])]
    )
    for name in required_checks:
        receipt = state["checks"].get(name)
        if (
            receipt is None
            or receipt.get("sha") != head_sha
            or receipt.get("exit_code") != 0
            or receipt.get("command") != _check_definition(manifest, name)["command"]
        ):
            raise ControlError(f"missing passing {name} receipt for head SHA {head_sha}")
    if definition.get("risk") == "novel":
        current_reviews = [
            review for review in state["reviews"] if review.get("head_sha") == head_sha
        ]
        if not current_reviews:
            raise ControlError(f"missing passing independent review for head SHA {head_sha}")
        passing_review = current_reviews[-1]
        if passing_review.get("verdict") != "pass":
            raise ControlError(
                f"latest independent review for head SHA {head_sha} is "
                f"{passing_review.get('verdict')}, not pass"
            )
        if passing_review.get("reviewer", {}).get("family") == manifest.get("models", {}).get(
            "worker", {}
        ).get("family"):
            raise ControlError("passing review is not independent from the worker model family")
    changed_files = snapshot.get("changed_files")
    if not isinstance(changed_files, list) or not all(
        isinstance(path, str) for path in changed_files
    ):
        raise ControlError("PR snapshot changed_files must be a string array")
    if len(changed_files) != len(set(changed_files)):
        raise ControlError("PR snapshot changed_files contains duplicates")
    changed_files_total = snapshot.get("changed_files_total")
    if (
        isinstance(changed_files_total, bool)
        or not isinstance(changed_files_total, int)
        or changed_files_total < 0
    ):
        raise ControlError("PR snapshot changed_files_total must be a non-negative integer")
    if changed_files_total != len(changed_files):
        raise ControlError(
            f"PR snapshot changed_files_total {changed_files_total} does not "
            f"match {len(changed_files)} files"
        )
    declarations = _load_json(args.declarations) if args.declarations is not None else {}
    if not all(
        isinstance(path, str) and path and isinstance(reason, str) and reason.strip()
        for path, reason in declarations.items()
    ):
        raise ControlError("accept declarations must map non-empty paths to non-empty reasons")
    forbidden_patterns = [
        *manifest.get("protected_paths", []),
        *manifest.get("no_go_paths", []),
        *definition.get("forbidden_paths", []),
    ]
    out_of_lane: set[str] = set()
    for path in changed_files:
        path_object = Path(path)
        if path_object.is_absolute() or ".." in path_object.parts:
            raise ControlError(f"invalid changed path: {path}")
        if any(_path_matches(path, pattern) for pattern in forbidden_patterns):
            raise ControlError(f"hard-forbidden changed path: {path}")
        for other_task, other_state in states.items():
            if other_task == task or other_state["status"] not in LIVE_TASK_STATUSES:
                continue
            other_definition = manifest["tasks"][other_task]
            if definition.get("repo") != other_definition.get("repo"):
                continue
            if any(_path_matches(path, pattern) for pattern in other_definition.get("lane", [])):
                raise ControlError(
                    f"changed path {path} conflicts with live task {other_task} lane"
                )
        if not any(_path_matches(path, pattern) for pattern in definition.get("lane", [])):
            out_of_lane.add(path)
            reason = declarations.get(path)
            if not isinstance(reason, str) or not reason.strip():
                raise ControlError(f"out-of-lane path lacks a declaration: {path}")
    extra_declarations = sorted(set(declarations) - out_of_lane)
    if extra_declarations:
        raise ControlError(
            "declarations include paths that do not require an out-of-lane "
            f"declaration: {', '.join(extra_declarations)}"
        )
    evidence_digest = _digest(snapshot)
    event = _append_event(
        journal,
        manifest,
        "task_accepted",
        {
            "task": task,
            "head_sha": head_sha,
            "repo": repo,
            "pr_number": args.pr_number,
            "base_ref": base_ref,
            "pr_url": snapshot.get("pr_url"),
            "changed_files": changed_files,
            "declarations": declarations,
            "evidence_digest": evidence_digest,
            "github_check_provenance": snapshot["required_checks"],
        },
        args.expected_seq,
    )
    return {
        "head_sha": head_sha,
        "evidence_digest": evidence_digest,
        "pr_number": args.pr_number,
        "seq": event["seq"],
        "status": "accepted",
        "task": task,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--journal", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    hook = subparsers.add_parser("hook", help="run one Claude Code hook from a task envelope")
    hook.add_argument("mode", choices=("pre-tool-use", "stop", "session-start"))
    init = subparsers.add_parser("init", help="initialize a hash-chained run journal")
    init.add_argument("--predecessor-manifest", type=Path)
    init.add_argument("--predecessor-journal", type=Path)
    init.add_argument("--allow-recorded-replay", action="store_true")
    subparsers.add_parser("ready", help="print the next deterministic task frontier")
    subparsers.add_parser("status", help="print the materialized durable run state")
    start = subparsers.add_parser("start", help="start one task from the ready frontier")
    start.add_argument("task")
    start.add_argument("--base-sha", required=True)
    start.add_argument("--base-ref", required=True)
    start.add_argument("--base-repo", type=Path, required=True)
    start.add_argument("--branch", required=True)
    start.add_argument("--orca-task-id", required=True)
    start.add_argument("--dispatch-id", required=True)
    start.add_argument("--terminal-handle", required=True)
    start.add_argument("--worktree-id", required=True)
    start.add_argument("--worktree-path", type=Path, required=True)
    start.add_argument("--expected-seq", type=int, required=True)
    checkpoint = subparsers.add_parser(
        "checkpoint", help="record a commit confirmed on a remote ref"
    )
    checkpoint.add_argument("task")
    checkpoint.add_argument("--sha", required=True)
    checkpoint.add_argument("--remote-ref", required=True)
    checkpoint.add_argument("--repo", type=Path, required=True)
    checkpoint.add_argument("--expected-seq", type=int, required=True)
    run_check = subparsers.add_parser(
        "run-check", help="run one configured check against the pushed SHA"
    )
    run_check.add_argument("task")
    run_check.add_argument("--name", required=True)
    run_check.add_argument("--repo", type=Path, required=True)
    run_check.add_argument("--expected-seq", type=int, required=True)
    review_packet = subparsers.add_parser(
        "review-packet",
        help="issue a compact GitHub-backed packet for one novel task review",
    )
    review_packet.add_argument("task")
    review_packet.add_argument("--pr-number", type=int, required=True)
    review_packet.add_argument("--declarations", type=Path)
    review_packet.add_argument("--reviewer-dispatch-id", required=True)
    review_packet.add_argument("--reviewer-terminal-handle", required=True)
    review_packet.add_argument("--reviewer-worktree-id", required=True)
    review_packet.add_argument("--output", type=Path, required=True)
    review_packet.add_argument("--expected-seq", type=int, required=True)
    record_review = subparsers.add_parser(
        "record-review", help="record a structured review of the pushed SHA"
    )
    record_review.add_argument("task")
    record_review.add_argument("--packet", type=Path, required=True)
    record_review.add_argument("--review", type=Path, required=True)
    record_review.add_argument("--expected-seq", type=int, required=True)
    accept = subparsers.add_parser(
        "accept", help="collect and accept authoritative GitHub PR evidence"
    )
    accept.add_argument("task")
    accept.add_argument("--pr-number", type=int, required=True)
    accept.add_argument("--declarations", type=Path)
    accept.add_argument("--expected-seq", type=int, required=True)
    resolve_gate = subparsers.add_parser(
        "resolve-gate", help="record a pinned planner decision for a churn gate"
    )
    resolve_gate.add_argument("task")
    resolve_gate.add_argument("--decision", type=Path, required=True)
    resolve_gate.add_argument("--expected-seq", type=int, required=True)
    merge = subparsers.add_parser(
        "merge", help="atomically merge the accepted immutable GitHub PR head"
    )
    merge.add_argument("task")
    merge.add_argument("--pr-number", type=int, required=True)
    merge.add_argument(
        "--merge-method",
        choices=("merge", "squash", "rebase"),
        default="squash",
    )
    merge.add_argument("--repo", type=Path, required=True)
    merge.add_argument("--main-ref", required=True)
    merge.add_argument("--expected-seq", type=int, required=True)
    reconcile_merge = subparsers.add_parser(
        "reconcile-merge",
        help="reconcile a durable merge intent against current GitHub state",
    )
    reconcile_merge.add_argument("task")
    reconcile_merge.add_argument("--repo", type=Path, required=True)
    reconcile_merge.add_argument("--main-ref", required=True)
    reconcile_merge.add_argument("--expected-seq", type=int, required=True)
    recover = subparsers.add_parser(
        "recover", help="inspect Git and classify live work from durable refs"
    )
    recover.add_argument("--repos", type=Path, required=True)
    recover.add_argument("--expected-seq", type=int, required=True)
    envelope = subparsers.add_parser("envelope", help="materialize a compact hook task envelope")
    envelope.add_argument("task", nargs="?")
    envelope.add_argument("--role", choices=("worker", "coordinator"), default="worker")
    envelope.add_argument("--output", type=Path, required=True)
    envelope.add_argument("--expected-seq", type=int, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    github_collector: GitHubCollector | None = None,
    github_merger: GitHubMerger | None = None,
    github_merge_state_collector: GitHubMergeStateCollector | None = None,
    refresh_start_base: bool = True,
    refresh_checkpoint_remote: bool = True,
    refresh_check_remote: bool = True,
    refresh_recovery_remotes: bool = True,
) -> int:
    args = _build_parser().parse_args(argv)
    collector = github_evidence.collect_pr_ci if github_collector is None else github_collector
    merger = github_evidence.merge_pr if github_merger is None else github_merger
    merge_state_collector = (
        github_evidence.collect_pr_merge_state
        if github_merge_state_collector is None
        else github_merge_state_collector
    )
    try:
        if args.command == "hook":
            return _run_hook(args.mode)
        if args.manifest is None or args.journal is None:
            raise ControlError("--manifest and --journal are required")
        manifest = _load_manifest(args.manifest)
        if args.command == "init":
            sources = manifest.get("sources")
            if (
                isinstance(sources, dict)
                and sources.get("authority") == "recorded_replay"
                and not args.allow_recorded_replay
            ):
                raise ControlError("recorded-replay manifest init requires --allow-recorded-replay")
            lineage = _validate_init_lineage(
                manifest,
                predecessor_manifest_path=args.predecessor_manifest,
                predecessor_journal_path=args.predecessor_journal,
                successor_journal_path=args.journal,
            )
            event = _initial_event(manifest, lineage=lineage)
            _write_new_journal(args.journal, event)
            result = {
                "journal": str(args.journal),
                "ready": _ready(manifest, [event])["ready"],
                "run_id": manifest.get("run_id"),
                "seq": 0,
            }
        elif args.command == "ready":
            events = _load_events(args.journal, manifest)
            result = _ready(manifest, events)
        elif args.command == "status":
            events = _load_events(args.journal, manifest)
            result = _status(manifest, events)
        elif args.command == "start":
            events = _load_events(args.journal, manifest)
            result = _start_task(
                manifest,
                events,
                args.journal,
                args,
                refresh_base=refresh_start_base,
            )
        elif args.command == "checkpoint":
            events = _load_events(args.journal, manifest)
            result = _checkpoint_task(
                manifest,
                events,
                args.journal,
                args,
                refresh_remote=refresh_checkpoint_remote,
            )
        elif args.command == "run-check":
            events = _load_events(args.journal, manifest)
            result = _run_check(
                manifest,
                events,
                args.journal,
                args,
                refresh_remote=refresh_check_remote,
            )
        elif args.command == "review-packet":
            events = _load_events(args.journal, manifest)
            result = _review_packet(
                manifest,
                events,
                args.journal,
                args,
                collector,
            )
        elif args.command == "record-review":
            events = _load_events(args.journal, manifest)
            result = _record_review(manifest, events, args.journal, args)
        elif args.command == "accept":
            events = _load_events(args.journal, manifest)
            result = _accept_task(
                manifest,
                events,
                args.journal,
                args,
                collector,
            )
        elif args.command == "resolve-gate":
            events = _load_events(args.journal, manifest)
            result = _resolve_gate(manifest, events, args.journal, args)
        elif args.command == "merge":
            events = _load_events(args.journal, manifest)
            result = _merge_task(
                manifest,
                events,
                args.journal,
                args,
                collector,
                merger,
                refresh_remote=github_merger is None,
            )
        elif args.command == "reconcile-merge":
            events = _load_events(args.journal, manifest)
            result = _reconcile_merge(
                manifest,
                events,
                args.journal,
                args,
                merge_state_collector,
                refresh_remote=github_merge_state_collector is None,
            )
        elif args.command == "recover":
            events = _load_events(args.journal, manifest)
            result = _recover(
                manifest,
                events,
                args.journal,
                args,
                refresh_remotes=refresh_recovery_remotes,
            )
        else:
            events = _load_events(args.journal, manifest)
            result = _write_task_envelope(args.manifest, manifest, events, args.journal, args)
    except ControlError as exc:
        error = {"error": str(exc), **exc.details}
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
