#!/usr/bin/env python3
"""Commit and push durable orchestration-control state from its dedicated worktree."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class SyncError(RuntimeError):
    """The state worktree cannot be published safely."""


def _run(repo: Path, *argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *argv], cwd=repo, text=True, capture_output=True, check=False
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SyncError(f"git {' '.join(argv)} failed: {detail}")
    return completed


def synchronize(repo: Path, *, message: str) -> dict[str, object]:
    repo = repo.resolve()
    if not repo.is_dir():
        raise SyncError(f"state worktree does not exist: {repo}")
    _run(repo, "rev-parse", "--is-inside-work-tree")
    _run(repo, "add", "--", ".orchestration")
    staged = _run(repo, "diff", "--cached", "--quiet", check=False)
    committed = staged.returncode == 1
    if staged.returncode not in {0, 1}:
        raise SyncError(staged.stderr.strip() or "cannot inspect staged state")
    if committed:
        _run(repo, "commit", "-m", message)
    branch = _run(repo, "branch", "--show-current").stdout.strip()
    if not branch:
        raise SyncError("state worktree is detached")
    upstream = _run(
        repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False
    )
    # A state worktree branched from `origin/main` inherits `origin/main` as its
    # upstream, so a bare `git push` either fails (push.default=simple) or targets
    # the wrong branch (push.default=upstream). Only take the bare path when the
    # upstream is genuinely this branch; otherwise publish it explicitly.
    tracks_same_branch = (
        upstream.returncode == 0 and upstream.stdout.strip() == f"origin/{branch}"
    )
    if tracks_same_branch:
        _run(repo, "push")
    else:
        _run(repo, "push", "-u", "origin", branch)
    return {
        "branch": branch,
        "committed": committed,
        "head": _run(repo, "rev-parse", "HEAD").stdout.strip(),
        "repo": str(repo),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--message", default="chore(orchestration): persist control state")
    args = parser.parse_args(argv)
    try:
        result = synchronize(args.repo, message=args.message)
    except SyncError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
