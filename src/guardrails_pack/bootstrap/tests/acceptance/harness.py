"""Run commands, copy trees, and read the gate, for every assertion of #81.

Nothing here states an assertion. This module gives each test module the same
five services: one process runner, the git readings, a tree copier that keeps
runtime output out of the copy, a reader of the gate outcome per hook, and the
one environment every subprocess runs in.

A subprocess must never inherit this test run's virtual environment, because a
projected project has its own. `environment` therefore drops the four variables
that a `uv run` or a `just` recipe exports, and it adds the throwaway tool
locations of the harness.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
from typing import cast

__all__ = [
    "GATE_CONFIG",
    "Outcome",
    "copy_tree",
    "environment",
    "failing_hooks",
    "gate",
    "git",
    "hook_ids",
    "make_repository",
    "porcelain",
    "present_files",
    "run",
    "sync",
    "tracked_files",
]

GATE_CONFIG = "pack/configs/prek.toml"
# The variables a `uv run` or a `just` recipe exports. A subprocess that inherits
# one of them reads this tree's virtual environment instead of its own.
INHERITED = ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH", "PYTHONPYCACHEPREFIX")
# Runtime output that no copy needs: git, the virtual environment, and every
# tool cache. A copy carries release content only, so a defect tree costs one
# `uv sync` from the warm cache rather than a full resolution.
UNCOPIED = frozenset(
    {
        ".basedpyright",
        ".git",
        ".hypothesis",
        ".import_linter_cache",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
    }
)
VERDICT = re.compile(r"^(?P<name>.+?)\.{3,}(?P<verdict>Passed|Failed|Skipped)$")
FAILED = "Failed"
LOCAL_REPOSITORY = "local"
COMMIT_NAME = "Acceptance Suite"
COMMIT_EMAIL = "acceptance@localhost"


@dataclass(frozen=True, slots=True)
class Outcome:
    """The whole result of one command: its code and both of its streams."""

    code: int
    out: str
    err: str

    @property
    def text(self) -> str:
        """Both streams together, for a search that does not care which one."""
        return f"{self.out}{self.err}"


def environment(**overrides: str) -> dict[str, str]:
    """This process environment, without the four inherited variables."""
    base = {key: value for key, value in os.environ.items() if key not in INHERITED}
    base.update(overrides)
    return base


def run(command: Sequence[str], cwd: Path, **overrides: str) -> Outcome:
    """Run one command in *cwd* and report its code and both streams."""
    completed = subprocess.run(
        tuple(command),
        cwd=cwd,
        env=environment(**overrides),
        capture_output=True,
        text=True,
        check=False,
    )
    return Outcome(completed.returncode, completed.stdout, completed.stderr)


def git(tree: Path, *arguments: str) -> Outcome:
    """Run one git command in *tree*."""
    return run(("git", *arguments), tree)


def porcelain(tree: Path) -> tuple[str, ...]:
    """Every line of `git status --porcelain`, which is empty on a clean tree."""
    outcome = git(tree, "status", "--porcelain")
    return tuple(line for line in outcome.out.splitlines() if line.strip())


def tracked_files(tree: Path) -> tuple[str, ...]:
    """Every path git tracks, which is exactly what an archive of `HEAD` ships."""
    return tuple(sorted(line for line in git(tree, "ls-files").out.splitlines() if line))


def present_files(tree: Path) -> tuple[str, ...]:
    """Every release file of *tree*: tracked or new, never ignored.

    A projected tree is measured before its first commit, so `--cached` can be
    empty. `--others --exclude-standard` reads the same `.gitignore` that the
    projection carried, so a virtual environment and every tool cache stay out.
    """
    outcome = git(tree, "ls-files", "--cached", "--others", "--exclude-standard")
    return tuple(sorted({line for line in outcome.out.splitlines() if line}))


def _ignored(path: Path, root: Path) -> bool:
    return any(part in UNCOPIED for part in path.relative_to(root).parts)


def copy_tree(source: Path, destination: Path) -> Path:
    """Copy the release content of *source*, leaving every runtime output behind."""
    for item in sorted(source.rglob("*")):
        if _ignored(item, source) or not item.is_file():
            continue
        target = destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(item, target)
    return destination


def make_repository(tree: Path, message: str = "Baseline") -> Path:
    """Turn *tree* into a git repository with exactly one commit."""
    _ = git(tree, "init", "--quiet", "--initial-branch=main")
    _ = git(tree, "config", "user.name", COMMIT_NAME)
    _ = git(tree, "config", "user.email", COMMIT_EMAIL)
    _ = git(tree, "add", "--all")
    _ = git(tree, "commit", "--quiet", "--message", message)
    return tree


def sync(tree: Path) -> Outcome:
    """Give *tree* its own virtual environment from the lockfile it carries."""
    return run(("uv", "sync", "--all-groups"), tree)


def hook_ids(tree: Path) -> dict[str, str]:
    """The display name of each local gate hook, mapped to its id."""
    config = cast("dict[str, object]", tomllib.loads((tree / GATE_CONFIG).read_text("utf-8")))
    repositories = cast("list[dict[str, object]]", config["repos"])
    return {
        str(hook["name"]): str(hook["id"])
        for repository in repositories
        if repository.get("repo") == LOCAL_REPOSITORY
        for hook in cast("list[dict[str, object]]", repository["hooks"])
    }


def gate(tree: Path, *hooks: str) -> Outcome:
    """Run the whole gate of *tree*, or only the named hooks."""
    return run(("uv", "run", "prek", "run", "--all-files", "-c", GATE_CONFIG, *hooks), tree)


def _verdicts(report: str) -> Iterable[tuple[str, str]]:
    for line in report.splitlines():
        found = VERDICT.match(line.strip())
        if found is not None:
            yield found.group("name"), found.group("verdict")


def failing_hooks(tree: Path, outcome: Outcome | None = None) -> frozenset[str]:
    """The id of every gate hook of *tree* that failed, by its own name.

    A hook the gate declares locally is reported by its id. Any other failing
    hook keeps its display name, so a failure can never be lost in translation.
    """
    report = gate(tree) if outcome is None else outcome
    known: Mapping[str, str] = hook_ids(tree)
    return frozenset(
        known.get(name, name) for name, verdict in _verdicts(report.text) if verdict == FAILED
    )
