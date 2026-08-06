"""One local command, run without the caller's git context.

A git hook exports `GIT_DIR` and `GIT_INDEX_FILE`. Without this scrub, a `git
add` inside a new project writes to the calling repository's index, so every
command here runs with those variables removed.

Each program is resolved on `PATH` first, and the resolved path is what runs. A
failure of either kind raises `OSError`. `_foundation.cli_outcomes` states the
exit code and the envelope that failure maps to.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

__all__ = ["LocalCommands", "environment_without_git_context", "output"]

# Every variable that can bind a nested git command to the caller's repository.
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
LOCAL_GIT_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
ENCODING = "utf-8"


def _binds_to_caller(key: str) -> bool:
    return key in LOCAL_GIT_ENVIRONMENT or key.startswith(LOCAL_GIT_PREFIXES)


def environment_without_git_context() -> dict[str, str]:
    """The process environment, without the git context of a calling repository."""
    return {key: value for key, value in os.environ.items() if not _binds_to_caller(key)}


def _resolve(program: str, command: Sequence[str], directory: Path) -> str:
    found = shutil.which(program)
    if found is None:
        shown = " ".join(command)
        message = f"'{program}' was not found on PATH."
        raise OSError(f"{message} Install it, then run this in '{directory}': {shown}")
    return found


def _completed(
    command: Sequence[str], directory: Path, *, capture: bool
) -> subprocess.CompletedProcess[bytes]:
    """The one place in this capability that starts a process."""
    resolved = _resolve(command[0], command, directory)
    return subprocess.run(
        [resolved, *command[1:]],
        cwd=directory,
        env=environment_without_git_context(),
        capture_output=capture,
        check=False,
    )


def _ended(command: Sequence[str], directory: Path, code: int) -> OSError:
    shown = " ".join(command)
    ended = f"'{shown}' ended with {code} in '{directory}'."
    return OSError(f"{ended} Correct the cause, then run that command there.")


def output(command: Sequence[str], directory: Path) -> bytes:
    """Run one command and return its standard output. Raise `OSError` on failure."""
    completed = _completed(command, directory, capture=True)
    if completed.returncode != 0:
        raise _ended(command, directory, completed.returncode)
    return completed.stdout


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalCommands:
    """Run one local command in one directory. Nothing here opens a socket."""

    def run(self, command: Sequence[str], directory: Path, /) -> None:
        """Run one command. Raise `OSError` when it is absent or ends non-zero."""
        completed = _completed(command, directory, capture=False)
        if completed.returncode != 0:
            raise _ended(command, directory, completed.returncode)

    def succeeds(self, command: Sequence[str], directory: Path, /) -> bool:
        """Run one command and report whether it ended with zero."""
        return _completed(command, directory, capture=True).returncode == 0

    def read(self, command: Sequence[str], directory: Path, /) -> str:
        """Run one command and return its standard output as text."""
        return output(command, directory).decode(ENCODING, errors="replace")
