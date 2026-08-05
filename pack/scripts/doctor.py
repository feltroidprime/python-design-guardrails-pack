#!/usr/bin/env python3
"""Fast, non-interactive pre-launch checks for a generated repository."""

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Literal

from scripts.quality_gate import inspect_prek_hooks

NETWORK_TIMEOUT_SECONDS = 2.0
LOCAL_TIMEOUT_SECONDS = 2.0
AHEAD_BEHIND_FIELD_COUNT = 2
OFFLINE_MARKERS = (
    "connection refused",
    "could not resolve host",
    "could not resolve hostname",
    "error connecting",
    "failed to connect",
    "network is unreachable",
    "no route to host",
    "temporary failure in name resolution",
    "timed out",
    "timeout",
)
GIT_STATUS_COMMAND = ("git", "status", "--porcelain=v1", "-z", "--untracked-files=normal")
GIT_ORIGIN_COMMAND = ("git", "remote", "get-url", "origin")
GIT_ORIGIN_HEAD_COMMAND = (
    "git",
    "symbolic-ref",
    "--quiet",
    "--short",
    "refs/remotes/origin/HEAD",
)
GH_AUTH_COMMAND = ("gh", "auth", "status")
UV_SYNC_COMMAND = ("uv", "sync", "--check")

type Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Probe:
    status: Status
    name: str
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_command(
    command: tuple[str, ...],
    root: Path,
    *,
    timeout: float = LOCAL_TIMEOUT_SECONDS,
    environment: dict[str, str] | None = None,
) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(
            returncode=127,
            stdout="",
            stderr=f"{command[0]} was not found on PATH",
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            returncode=124,
            stdout="",
            stderr=f"timed out after {timeout:g}s",
            timed_out=True,
        )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def is_offline(result: CommandResult) -> bool:
    if result.timed_out:
        return True
    message = f"{result.stdout}\n{result.stderr}".lower()
    return any(marker in message for marker in OFFLINE_MARKERS)


def hooks_probe(root: Path) -> Probe:
    inspection = inspect_prek_hooks(root)
    if not inspection.configured:
        return Probe(status="warn", name="hooks", detail="skipped: prek policy is not configured")
    status: Status = "ok" if inspection.installed else "fail"
    return Probe(status=status, name="hooks", detail=inspection.detail)


def working_tree_probe(root: Path) -> Probe:
    result = run_command(GIT_STATUS_COMMAND, root)
    if result.returncode != 0:
        return Probe(status="fail", name="working-tree", detail="git status failed")
    entries = tuple(entry for entry in result.stdout.split("\0") if entry)
    if entries:
        return Probe(
            status="fail",
            name="working-tree",
            detail=f"dirty ({len(entries)} entries)",
        )
    return Probe(status="ok", name="working-tree", detail="clean")


def local_default_branch(root: Path) -> str:
    origin_head = run_command(GIT_ORIGIN_HEAD_COMMAND, root)
    if origin_head.returncode == 0 and origin_head.stdout.strip().startswith("origin/"):
        return origin_head.stdout.strip().removeprefix("origin/")
    for candidate in ("main", "master"):
        command = ("git", "show-ref", "--verify", "--quiet", f"refs/heads/{candidate}")
        if run_command(command, root).returncode == 0:
            return candidate
    current = run_command(("git", "symbolic-ref", "--quiet", "--short", "HEAD"), root)
    return current.stdout.strip()


def branch_sync_probe(root: Path) -> Probe:
    origin = run_command(GIT_ORIGIN_COMMAND, root)
    if origin.returncode != 0:
        return Probe(status="warn", name="branch-sync", detail="skipped: origin is not configured")
    branch = local_default_branch(root)
    if not branch:
        return Probe(status="fail", name="branch-sync", detail="local default branch is unresolved")
    fetch_environment = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
    }
    fetch = run_command(
        (
            "git",
            "fetch",
            "--quiet",
            "--no-write-fetch-head",
            "origin",
            f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
        ),
        root,
        timeout=NETWORK_TIMEOUT_SECONDS,
        environment=fetch_environment,
    )
    if fetch.returncode != 0:
        status: Status = "warn" if is_offline(fetch) else "fail"
        prefix = "skipped: offline" if status == "warn" else "fetch failed"
        return Probe(status=status, name="branch-sync", detail=f"{prefix} ({branch})")
    counts = run_command(
        (
            "git",
            "rev-list",
            "--left-right",
            "--count",
            f"refs/heads/{branch}...refs/remotes/origin/{branch}",
        ),
        root,
    )
    if counts.returncode != 0:
        return Probe(status="fail", name="branch-sync", detail=f"cannot compare {branch}")
    fields = counts.stdout.split()
    if len(fields) != AHEAD_BEHIND_FIELD_COUNT or not all(field.isdigit() for field in fields):
        return Probe(status="fail", name="branch-sync", detail="invalid ahead/behind result")
    ahead, behind = (int(field) for field in fields)
    status = "ok" if ahead == 0 and behind == 0 else "fail"
    return Probe(
        status=status,
        name="branch-sync",
        detail=f"{branch} ahead={ahead} behind={behind}",
    )


def gh_auth_probe(root: Path) -> Probe:
    if shutil.which("gh") is None:
        return Probe(status="warn", name="gh-auth", detail="skipped: gh is not installed")
    environment = {
        **os.environ,
        "GH_PROMPT_DISABLED": "1",
        "NO_COLOR": "1",
    }
    result = run_command(
        GH_AUTH_COMMAND,
        root,
        timeout=NETWORK_TIMEOUT_SECONDS,
        environment=environment,
    )
    if result.returncode == 0:
        return Probe(status="ok", name="gh-auth", detail="authenticated")
    if is_offline(result):
        return Probe(status="warn", name="gh-auth", detail="skipped: GitHub is offline")
    return Probe(status="fail", name="gh-auth", detail="authentication is invalid")


def uv_sync_probe(root: Path) -> Probe:
    environment = {
        **os.environ,
        "UV_OFFLINE": "1",
        "UV_NO_PROGRESS": "1",
    }
    result = run_command(UV_SYNC_COMMAND, root, environment=environment)
    if result.returncode == 0:
        return Probe(
            status="ok",
            name="uv-sync",
            detail="environment and lockfile are consistent",
        )
    return Probe(status="fail", name="uv-sync", detail="uv sync --check failed")


def python_version_probe(root: Path) -> Probe:
    version_file = root / ".python-version"
    if not version_file.is_file():
        return Probe(
            status="warn",
            name="python-version",
            detail="skipped: .python-version is not configured",
        )
    expected = version_file.read_text(encoding="utf-8").strip()
    actual = platform.python_version()
    if not expected:
        return Probe(status="fail", name="python-version", detail=".python-version is empty")
    matches = actual == expected or (expected.count(".") == 1 and actual.startswith(f"{expected}."))
    status: Status = "ok" if matches else "fail"
    verb = "matches" if matches else "does not match"
    return Probe(
        status=status,
        name="python-version",
        detail=f"{actual} {verb} {expected}",
    )


def probes(root: Path) -> tuple[Probe, ...]:
    return (
        hooks_probe(root),
        working_tree_probe(root),
        branch_sync_probe(root),
        gh_auth_probe(root),
        uv_sync_probe(root),
        python_version_probe(root),
    )


def main() -> int:
    root = Path.cwd()
    results = probes(root)
    for probe in results:
        print(f"{probe.status} {probe.name}: {probe.detail}")
    failures = sum(probe.status == "fail" for probe in results)
    warnings = sum(probe.status == "warn" for probe in results)
    verdict: Status = "fail" if failures else "ok"
    print(f"{verdict} verdict: {failures} failures, {warnings} warnings")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
