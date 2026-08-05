#!/usr/bin/env python3
"""Create a changelog-backed template release tag."""

import os
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
TAG_PATTERN = re.compile(r"v\d+\.\d+\.\d+\Z")
LOCAL_GIT_ENVIRONMENT = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)


def is_local_git_environment(key: str) -> bool:
    """Return whether *key* can bind Git to an inherited repository."""
    return key in LOCAL_GIT_ENVIRONMENT or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))


def git(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run Git in the pack repository without hiding diagnostics."""
    return subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        env={key: value for key, value in os.environ.items() if not is_local_git_environment(key)},
        capture_output=True,
        text=True,
        check=False,
    )


def fail(message: str) -> int:
    print(f"Release refused: {message}", file=sys.stderr)
    return 2


def main(arguments: list[str] | None = None) -> int:
    args = sys.argv[1:] if arguments is None else arguments
    if len(args) != 1 or TAG_PATTERN.fullmatch(args[0]) is None:
        return fail("version must be one PEP 440 release tag in the form vX.Y.Z")
    version = args[0]

    changelog = REPO_ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        return fail("CHANGELOG.md does not exist")
    heading = f"## [{version}]"
    if not any(
        line.startswith(heading) for line in changelog.read_text(encoding="utf-8").splitlines()
    ):
        return fail(f"CHANGELOG.md has no '{heading}' entry")

    status = git("status", "--porcelain")
    if status.returncode != 0:
        return fail(status.stderr.strip() or "git status failed")
    if status.stdout:
        return fail("the working tree is not clean")

    existing = git("rev-parse", "--quiet", "--verify", f"refs/tags/{version}")
    if existing.returncode == 0:
        return fail(f"tag {version} already exists")

    tagged = git("tag", "--annotate", version, "--message", f"Template release {version}")
    if tagged.returncode != 0:
        return fail(tagged.stderr.strip() or "git tag failed")
    print(f"Created template release tag {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
