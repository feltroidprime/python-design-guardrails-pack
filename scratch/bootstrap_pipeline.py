#!/usr/bin/env python3
"""The git, setup, commit, and `gh` pipeline of the One-shot Bootstrap.

Ticket I1 kept this code on the scratch path. Ticket I8 moves it into
`src/guardrails_pack/bootstrap/`, where it becomes the second half of the `init`
function of `api.py`. The first half is Terminal Projection, which I8 writes.

What this module holds, and why:

- `is_local_git_environment` and `environment_without_local_git_context` stop a
  git command in a new project binding to the caller's repository. A git hook
  exports `GIT_DIR` and `GIT_INDEX_FILE`, so a nested `git add` writes to the
  wrong index without this scrub. `pack/scripts/release.py` holds a second copy.
- `initialize_git_repository`, `run_setup`, and `create_initial_commit` are the
  three ordered steps of `init` step 5 of #85 section 3.3.
- `github_create_command` is `init` step 7. It runs only for `--github`.

Two changes I8 must make:

1. The recipe is named `bootstrap` today. C14 of #85 renames it to `setup`,
   which ticket I3 applies. Read `SETUP_RECIPE` after I3 lands.
2. `--no-github` and `--no-git` do not survive. CLI004 forbids a `bool`
   parameter that defaults to `True`, so the network step is opt-in through
   `--github`, and `--public` selects the visibility. See A3 of #85.

The `plumbum` half of the original context manager died with the template
engine. Only the `os.environ` scrub survives.
"""

from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading

PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
GIT_COMMIT_MESSAGE = "Initial commit from pyrepo"
SETUP_RECIPE = "bootstrap"
GIT_CONTEXT_LOCK = threading.RLock()
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
    """Return whether *key* can bind git commands to a caller's repository."""
    return key in LOCAL_GIT_ENVIRONMENT or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))


def derive_package_name(project_name: str) -> str:
    """Return the import package derived from the project name."""
    return project_name.replace("-", "_").replace(".", "_")


def environment_without_local_git_context() -> dict[str, str]:
    """Copy the process environment without a calling repository's git context."""
    return {key: value for key, value in os.environ.items() if not is_local_git_environment(key)}


@contextmanager
def without_local_git_context() -> Generator[None]:
    """Keep a nested git command out of the caller's index."""
    with GIT_CONTEXT_LOCK:
        inherited = {
            key: os.environ.pop(key) for key in tuple(os.environ) if is_local_git_environment(key)
        }
        try:
            yield
        finally:
            os.environ.update(inherited)


def run_command(command: list[str], cwd: Path) -> str | None:
    """Run a command in *cwd*. Return an error message, or None on success."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment_without_local_git_context(),
        check=False,
    )
    if completed.returncode != 0:
        return f"'{' '.join(command)}' exited with {completed.returncode}."
    return None


def initialize_git_repository(output: Path) -> str | None:
    """Initialize git in *output*. Return an error message, or None on success."""
    if shutil.which("git") is None:
        return "git was not found on PATH; cannot initialize a git repository."
    return run_command(["git", "init", "--quiet", "--initial-branch=main"], output)


def run_setup(output: Path) -> str | None:
    """Install the dependencies and the hooks of the new project."""
    if shutil.which("just") is None:
        return "'just' was not found on PATH; cannot set up the repository."
    return run_command(["just", SETUP_RECIPE], output)


def create_initial_commit(output: Path) -> str | None:
    """Commit the baseline. Return an error message, or None on success."""
    identity: list[str] = []
    email = subprocess.run(
        ["git", "config", "--get", "user.email"],
        cwd=output,
        env=environment_without_local_git_context(),
        capture_output=True,
        check=False,
    )
    if email.returncode != 0:
        identity = ["-c", "user.name=pyrepo", "-c", "user.email=pyrepo@localhost"]
    for command in (
        ["git", "add", "--all"],
        ["git", *identity, "commit", "--quiet", "--message", GIT_COMMIT_MESSAGE],
    ):
        error = run_command(command, output)
        if error is not None:
            return error
    return None


def prepare_repository(output: Path) -> str | None:
    """Initialize, set up, and commit a ready-to-use repository."""
    for name, step in (
        ("Git initialization", initialize_git_repository),
        ("Setup", run_setup),
        ("Initial commit", create_initial_commit),
    ):
        error = step(output)
        if error is not None:
            return f"{name} failed: {error}"
    return None


def github_create_command(project_name: str, *, public: bool) -> list[str]:
    """Return the `gh` command that creates and pushes the new repository."""
    visibility = "--public" if public else "--private"
    return [
        "gh",
        "repo",
        "create",
        project_name,
        visibility,
        "--source",
        ".",
        "--remote",
        "origin",
        "--push",
    ]


def publish_to_github(project_name: str, output: Path, *, public: bool) -> str | None:
    """Create the GitHub repository and push. Return an error message, or None."""
    command = github_create_command(project_name, public=public)
    if shutil.which("gh") is None:
        return f"gh was not found on PATH. Run this from inside the repository:\n  {' '.join(command)}"
    error = run_command(command, output)
    if error is not None:
        return (
            f"GitHub repository creation failed: {error}\n"
            "Correct the cause (for example 'gh auth login', or a name collision).\n"
            f"Then run this from inside the repository:\n  {' '.join(command)}"
        )
    return None
