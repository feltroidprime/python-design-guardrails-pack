#!/usr/bin/env python3
"""Render validated Orca CLI argument vectors without executing them."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any


class AdapterError(ValueError):
    """The structured operation cannot be rendered safely."""


TASK_STATUSES = {"pending", "ready", "dispatched", "completed", "failed", "blocked"}


def _check_keys(operation: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(operation) - allowed)
    if unknown:
        raise AdapterError(f"unknown fields: {', '.join(unknown)}")


def _text(operation: Mapping[str, Any], field: str) -> str:
    value = operation.get(field)
    if not isinstance(value, str) or not value or "\x00" in value:
        raise AdapterError(f"{field} must be a non-empty string")
    return value


def _optional_text(operation: Mapping[str, Any], field: str) -> str | None:
    if field not in operation:
        return None
    return _text(operation, field)


def _boolean(operation: Mapping[str, Any], field: str, *, default: bool = False) -> bool:
    if field not in operation:
        return default
    value = operation[field]
    if not isinstance(value, bool):
        raise AdapterError(f"{field} must be a boolean")
    return value


def _positive_int(operation: Mapping[str, Any], field: str) -> int:
    value = operation.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AdapterError(f"{field} must be a positive integer")
    return value


def _string_array(
    operation: Mapping[str, Any],
    field: str,
    *,
    required: bool = False,
    nonempty: bool = False,
) -> list[str] | None:
    if field not in operation:
        if required:
            raise AdapterError(f"{field} is required")
        return None
    value = operation[field]
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item or "\x00" in item for item in value
    ):
        raise AdapterError(f"{field} must be a JSON array of non-empty strings")
    if nonempty and not value:
        raise AdapterError(f"{field} must not be empty")
    return value


def _csv_array(
    operation: Mapping[str, Any],
    field: str,
    *,
    required: bool = False,
    nonempty: bool = False,
) -> list[str] | None:
    values = _string_array(
        operation,
        field,
        required=required,
        nonempty=nonempty,
    )
    if values is not None and any("," in item for item in values):
        raise AdapterError(f"{field} entries must not contain commas")
    return values


def _json_text(value: Any, field: str) -> str:
    if not isinstance(value, dict):
        raise AdapterError(f"{field} must be a JSON object")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _validate_full_worktree_id(value: str, field: str) -> None:
    repo_id, separator, path = value.partition("::")
    if not separator or not repo_id or not path:
        raise AdapterError(f"{field} id selector must include the full repo-id::path")
    if not path.startswith("/"):
        raise AdapterError(f"{field} id selector must include an absolute worktree path")


def _worktree_selector(operation: Mapping[str, Any], field: str = "worktree") -> str:
    value = _text(operation, field)
    if value in {"active", "current"}:
        return value
    prefix, separator, payload = value.partition(":")
    if not separator or prefix not in {"id", "name", "path", "branch", "issue"} or not payload:
        raise AdapterError(f"{field} must be a documented worktree selector")
    if prefix == "id":
        _validate_full_worktree_id(payload, field)
    if prefix == "path" and not payload.startswith("/"):
        raise AdapterError(f"{field} path selector must be absolute")
    return value


def _parent_worktree_selector(operation: Mapping[str, Any]) -> str:
    field = "parent_worktree"
    value = _text(operation, field)
    for prefix in ("worktree:", "id:worktree:"):
        if value.startswith(prefix):
            _validate_full_worktree_id(value.removeprefix(prefix), field)
            return value
    for prefix in ("folder:", "id:folder:"):
        if value.startswith(prefix):
            if not value.removeprefix(prefix):
                raise AdapterError(f"{field} must be a documented parent-worktree selector")
            return value
    try:
        return _worktree_selector(operation, field)
    except AdapterError as exc:
        if "documented worktree selector" not in str(exc):
            raise
        raise AdapterError(f"{field} must be a documented parent-worktree selector") from None


def _repo_selector(operation: Mapping[str, Any]) -> str:
    value = _text(operation, "repo")
    prefix, separator, payload = value.partition(":")
    if not separator or prefix not in {"id", "path"} or not payload:
        raise AdapterError("repo must use an id: or path: selector")
    if prefix == "path" and not payload.startswith("/"):
        raise AdapterError("repo path selector must be absolute")
    return value


def _status(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable"})
    return [executable, "status", "--json"]


def _worktree_current(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable"})
    return [executable, "worktree", "current", "--json"]


def _worktree_show(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "worktree"})
    return [
        executable,
        "worktree",
        "show",
        "--worktree",
        _worktree_selector(operation),
        "--json",
    ]


def _worktree_create(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {
            "operation",
            "executable",
            "repo",
            "name",
            "parent_worktree",
            "no_parent",
            "base_branch",
            "agent",
            "setup",
        },
    )
    argv = [executable, "worktree", "create"]
    if "repo" in operation:
        argv.extend(["--repo", _repo_selector(operation)])
    argv.extend(["--name", _text(operation, "name")])
    parent = _parent_worktree_selector(operation) if "parent_worktree" in operation else None
    no_parent = _boolean(operation, "no_parent")
    if parent and no_parent:
        raise AdapterError("parent_worktree and no_parent are mutually exclusive")
    if parent:
        argv.extend(["--parent-worktree", parent])
    elif no_parent:
        argv.append("--no-parent")
    for field, flag in (
        ("base_branch", "--base-branch"),
        ("agent", "--agent"),
    ):
        if value := _optional_text(operation, field):
            argv.extend([flag, value])
    if setup := _optional_text(operation, "setup"):
        if setup not in {"run", "skip", "inherit"}:
            raise AdapterError("setup must be run, skip, or inherit")
        argv.extend(["--setup", setup])
    return [*argv, "--json"]


def _worktree_rm(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "worktree", "force"})
    argv = [
        executable,
        "worktree",
        "rm",
        "--worktree",
        _worktree_selector(operation),
    ]
    if _boolean(operation, "force"):
        argv.append("--force")
    return [*argv, "--json"]


def _terminal_create(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "worktree", "title", "command"},
    )
    return [
        executable,
        "terminal",
        "create",
        "--worktree",
        _worktree_selector(operation),
        "--title",
        _text(operation, "title"),
        "--command",
        _text(operation, "command"),
        "--json",
    ]


def _terminal_wait(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "terminal", "for", "timeout_ms"},
    )
    wait_for = _text(operation, "for")
    if wait_for not in {"tui-idle", "exit"}:
        raise AdapterError("for must be tui-idle or exit")
    return [
        executable,
        "terminal",
        "wait",
        "--terminal",
        _text(operation, "terminal"),
        "--for",
        wait_for,
        "--timeout-ms",
        str(_positive_int(operation, "timeout_ms")),
        "--json",
    ]


def _terminal_list(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "worktree"})
    return [
        executable,
        "terminal",
        "list",
        "--worktree",
        _worktree_selector(operation),
        "--json",
    ]


def _terminal_show(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "terminal"})
    return [
        executable,
        "terminal",
        "show",
        "--terminal",
        _text(operation, "terminal"),
        "--json",
    ]


def _terminal_stop(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "worktree"})
    return [
        executable,
        "terminal",
        "stop",
        "--worktree",
        _worktree_selector(operation),
        "--json",
    ]


def _orchestration_run(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {
            "operation",
            "executable",
            "spec",
            "from",
            "poll_interval_ms",
            "max_concurrent",
            "worktree",
        },
    )
    argv = [
        executable,
        "orchestration",
        "run",
        "--spec",
        _text(operation, "spec"),
    ]
    if from_handle := _optional_text(operation, "from"):
        argv.extend(["--from", from_handle])
    if "poll_interval_ms" in operation:
        argv.extend(
            [
                "--poll-interval-ms",
                str(_positive_int(operation, "poll_interval_ms")),
            ]
        )
    argv.extend(
        [
            "--max-concurrent",
            str(_positive_int(operation, "max_concurrent")),
            "--worktree",
            _worktree_selector(operation),
            "--json",
        ]
    )
    return argv


def _orchestration_run_stop(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable"})
    return [executable, "orchestration", "run-stop", "--json"]


def _task_create(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "spec", "deps", "parent"},
    )
    argv = [
        executable,
        "orchestration",
        "task-create",
        "--spec",
        _text(operation, "spec"),
    ]
    if deps := _string_array(operation, "deps"):
        argv.extend(["--deps", json.dumps(deps, separators=(",", ":"))])
    if parent := _optional_text(operation, "parent"):
        argv.extend(["--parent", parent])
    return [*argv, "--json"]


def _task_list(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "status", "ready", "brief"},
    )
    argv = [executable, "orchestration", "task-list"]
    if status := _optional_text(operation, "status"):
        if status not in TASK_STATUSES:
            raise AdapterError("status is not a documented task status")
        argv.extend(["--status", status])
    if _boolean(operation, "ready"):
        argv.append("--ready")
    if _boolean(operation, "brief"):
        argv.append("--brief")
    return [*argv, "--json"]


def _task_update(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "recovery", "task_id", "status", "result"},
    )
    if not _boolean(operation, "recovery"):
        raise AdapterError("task-update is available only for explicit recovery")
    status = _text(operation, "status")
    if status not in TASK_STATUSES:
        raise AdapterError("status is not a documented task status")
    argv = [
        executable,
        "orchestration",
        "task-update",
        "--id",
        _text(operation, "task_id"),
        "--status",
        status,
    ]
    if "result" in operation:
        argv.extend(["--result", _json_text(operation["result"], "result")])
    return [*argv, "--json"]


def _dispatch(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "task_id", "to", "inject"},
    )
    argv = [
        executable,
        "orchestration",
        "dispatch",
        "--task",
        _text(operation, "task_id"),
        "--to",
        _text(operation, "to"),
    ]
    if _boolean(operation, "inject", default=True):
        argv.append("--inject")
    return [*argv, "--json"]


def _dispatch_show(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "task_id"})
    return [
        executable,
        "orchestration",
        "dispatch-show",
        "--task",
        _text(operation, "task_id"),
        "--json",
    ]


def _check_wait(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "types", "timeout_ms"},
    )
    types = _csv_array(operation, "types", required=True, nonempty=True)
    assert types is not None
    return [
        executable,
        "orchestration",
        "check",
        "--wait",
        "--types",
        ",".join(types),
        "--timeout-ms",
        str(_positive_int(operation, "timeout_ms")),
        "--json",
    ]


def _ask(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {
            "operation",
            "executable",
            "to",
            "question",
            "options",
            "timeout_ms",
            "from",
        },
    )
    argv = [
        executable,
        "orchestration",
        "ask",
        "--to",
        _text(operation, "to"),
        "--question",
        _text(operation, "question"),
    ]
    if options := _csv_array(operation, "options", nonempty=True):
        argv.extend(["--options", ",".join(options)])
    argv.extend(["--timeout-ms", str(_positive_int(operation, "timeout_ms"))])
    if from_handle := _optional_text(operation, "from"):
        argv.extend(["--from", from_handle])
    return [*argv, "--json"]


def _reply(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "message_id", "body"})
    return [
        executable,
        "orchestration",
        "reply",
        "--id",
        _text(operation, "message_id"),
        "--body",
        _text(operation, "body"),
        "--json",
    ]


def _gate_create(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "task_id", "question", "options"},
    )
    options = _string_array(operation, "options", required=True, nonempty=True)
    assert options is not None
    return [
        executable,
        "orchestration",
        "gate-create",
        "--task",
        _text(operation, "task_id"),
        "--question",
        _text(operation, "question"),
        "--options",
        json.dumps(options, separators=(",", ":")),
        "--json",
    ]


def _gate_list(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(operation, {"operation", "executable", "task_id", "status"})
    argv = [executable, "orchestration", "gate-list"]
    if task_id := _optional_text(operation, "task_id"):
        argv.extend(["--task", task_id])
    if status := _optional_text(operation, "status"):
        argv.extend(["--status", status])
    return [*argv, "--json"]


def _gate_resolve(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {"operation", "executable", "gate_id", "resolution"},
    )
    return [
        executable,
        "orchestration",
        "gate-resolve",
        "--id",
        _text(operation, "gate_id"),
        "--resolution",
        _text(operation, "resolution"),
        "--json",
    ]


def _send_worker_done(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {
            "operation",
            "executable",
            "to",
            "subject",
            "body",
            "task_id",
            "dispatch_id",
            "files_modified",
            "report_path",
        },
    )
    files_modified = _string_array(operation, "files_modified", required=True)
    assert files_modified is not None
    payload: dict[str, Any] = {
        "taskId": _text(operation, "task_id"),
        "dispatchId": _text(operation, "dispatch_id"),
        "filesModified": files_modified,
    }
    if report_path := _optional_text(operation, "report_path"):
        payload["reportPath"] = report_path
    return [
        executable,
        "orchestration",
        "send",
        "--to",
        _text(operation, "to"),
        "--type",
        "worker_done",
        "--subject",
        _text(operation, "subject"),
        "--body",
        _text(operation, "body"),
        "--payload",
        json.dumps(payload, separators=(",", ":")),
        "--json",
    ]


def _send_heartbeat(operation: Mapping[str, Any], executable: str) -> list[str]:
    _check_keys(
        operation,
        {
            "operation",
            "executable",
            "to",
            "task_id",
            "dispatch_id",
            "phase",
        },
    )
    payload = {
        "taskId": _text(operation, "task_id"),
        "dispatchId": _text(operation, "dispatch_id"),
        "phase": _text(operation, "phase"),
    }
    return [
        executable,
        "orchestration",
        "send",
        "--to",
        _text(operation, "to"),
        "--type",
        "heartbeat",
        "--subject",
        "alive",
        "--payload",
        json.dumps(payload, separators=(",", ":")),
        "--json",
    ]


def build_argv(operation: Mapping[str, Any]) -> list[str]:
    """Return the exact Orca argv for one structured operation."""
    name = operation.get("operation")
    if not isinstance(name, str) or not name:
        raise AdapterError("operation must be a non-empty string")
    executable = _text(operation, "executable")
    builders = {
        "status": _status,
        "worktree-current": _worktree_current,
        "worktree-show": _worktree_show,
        "worktree-create": _worktree_create,
        "worktree-rm": _worktree_rm,
        "terminal-create": _terminal_create,
        "terminal-wait": _terminal_wait,
        "terminal-list": _terminal_list,
        "terminal-show": _terminal_show,
        "terminal-stop": _terminal_stop,
        "orchestration-run": _orchestration_run,
        "orchestration-run-stop": _orchestration_run_stop,
        "task-create": _task_create,
        "task-list": _task_list,
        "task-update": _task_update,
        "dispatch": _dispatch,
        "dispatch-show": _dispatch_show,
        "check-wait": _check_wait,
        "ask": _ask,
        "reply": _reply,
        "gate-create": _gate_create,
        "gate-list": _gate_list,
        "gate-resolve": _gate_resolve,
        "send-worker-done": _send_worker_done,
        "send-heartbeat": _send_heartbeat,
    }
    builder = builders.get(name)
    if builder is None:
        raise AdapterError("unsupported operation")
    return builder(operation, executable)


def main() -> int:
    """Read one JSON operation from stdin and emit one JSON result."""
    try:
        raw = json.load(sys.stdin)
        if not isinstance(raw, dict):
            raise AdapterError("operation must be a JSON object")
        argv = build_argv(raw)
    except (AdapterError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, separators=(",", ":")))
        return 2
    print(json.dumps({"argv": argv}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
