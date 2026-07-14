"""Per-arm workspace preparation.

Both arms start as git repositories so the builder sees the same "fresh repo"
situation; the only difference is the content: nothing versus the instantiated
template. Anything else (network installs, tool sync) happens later and is
timed separately, so setup cost is reported instead of hidden.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time

from copier import run_copy
from copier.errors import CopierError
from yaml import safe_dump, safe_load

from benchmarks.e2e.config import ARM_BARE, ARM_GUARDRAILS, BenchmarkConfig
from instantiate import environment_without_local_git_context, without_local_git_context

_GIT_IDENTITY = (
    "-c",
    "user.name=guardrails-benchmark",
    "-c",
    "user.email=guardrails-benchmark@localhost",
)
_LOCAL_GIT_ENVIRONMENT = {
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
}


def _is_local_git_environment(key: str) -> bool:
    return key in _LOCAL_GIT_ENVIRONMENT or key.startswith(
        ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
    )


def git_environment() -> dict[str, str]:
    """Return an environment in which Git discovers the requested workspace."""
    return {
        key: value
        for key, value in os.environ.items()
        if not _is_local_git_environment(key)
    }


class WorkspaceError(RuntimeError):
    """Workspace preparation failed; the benchmark cannot compare anything."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Workspace:
    arm: str
    path: Path
    setup_seconds: float
    setup_log: str
    template_identity: dict[str, object] | None = None


def _git(arguments: tuple[str, ...], cwd: Path) -> str:
    command = ("git", *_GIT_IDENTITY, *arguments)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=git_environment(),
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise WorkspaceError(
            f"'{' '.join(command)}' exited with {completed.returncode}: {completed.stderr.strip()}"
        )
    return completed.stdout


def _generate_from_template(
    cfg: BenchmarkConfig,
    destination: Path,
    repo_root: Path,
    *,
    template_source_root: Path | None = None,
    template_vcs_ref: str | None = None,
    template_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    answers = {
        "project_name": cfg.project.name,
        "package": cfg.project.package,
        **cfg.template.answers,
    }
    source_root = template_source_root or repo_root
    render_vcs_ref = template_vcs_ref or cfg.template.vcs_ref
    working_tree_version = None
    if template_identity is None and render_vcs_ref == "HEAD":
        described = subprocess.run(
            ("git", "describe", "--tags", "--always", "--dirty"),
            cwd=source_root,
            env=environment_without_local_git_context(),
            capture_output=True,
            text=True,
            check=False,
        )
        if described.returncode != 0 or not described.stdout.strip():
            raise WorkspaceError(
                "could not resolve current template working-tree identity: "
                + described.stderr.strip()
            )
        working_tree_version = described.stdout.strip()
    try:
        with without_local_git_context():
            run_copy(
                str(source_root),
                destination,
                data=answers,
                vcs_ref=render_vcs_ref,
                defaults=True,
                quiet=True,
                skip_tasks=True,
            )
    except (CopierError, ValueError) as error:
        raise WorkspaceError(f"template instantiation failed: {error}") from error

    answers_path = destination / ".copier-answers.yml"
    try:
        recorded = safe_load(answers_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise WorkspaceError(f"could not read Copier answers from {answers_path}: {error}") from error
    if not isinstance(recorded, dict) or not isinstance(recorded.get("_commit"), str):
        raise WorkspaceError(f"Copier answers in {answers_path} have no resolved _commit")
    if template_identity is not None:
        recorded["_src_path"] = str(repo_root)
        recorded["_commit"] = render_vcs_ref
        answers_path.write_text(
            "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"
            + safe_dump(recorded, sort_keys=False),
            encoding="utf-8",
        )
    identity = dict(template_identity) if template_identity is not None else {
        "version": working_tree_version or recorded["_commit"],
        "vcs_ref": cfg.template.vcs_ref,
    }
    identity.update({
        "variant": cfg.template.variant,
        "answers": {
            str(key): value
            for key, value in recorded.items()
            if not str(key).startswith("_")
        },
    })
    return identity


def prepare_workspace(
    arm: str,
    cfg: BenchmarkConfig,
    arms_dir: Path,
    *,
    repo_root: Path,
    template_source_root: Path | None = None,
    template_vcs_ref: str | None = None,
    template_identity: dict[str, object] | None = None,
) -> Workspace:
    """Create the arm's starting repository under `arms_dir/<arm>/workspace`."""
    started = time.monotonic()
    lines: list[str] = []
    destination = arms_dir / arm / "workspace"
    destination.mkdir(parents=True, exist_ok=False)

    resolved_template_identity = None
    if arm == ARM_GUARDRAILS:
        resolved_template_identity = _generate_from_template(
            cfg,
            destination,
            repo_root,
            template_source_root=template_source_root,
            template_vcs_ref=template_vcs_ref,
            template_identity=template_identity,
        )
        lines.append(f"instantiated template as {cfg.project.name} ({cfg.project.package})")
    elif arm != ARM_BARE:
        raise WorkspaceError(f"unknown arm {arm!r}")

    _git(("init", "--quiet", "--initial-branch=main"), destination)
    _git(("add", "--all"), destination)
    _git(("commit", "--quiet", "--allow-empty", "--message", f"benchmark start: {arm}"), destination)
    lines.append("git repository initialized on main")

    return Workspace(
        arm=arm,
        path=destination,
        setup_seconds=time.monotonic() - started,
        setup_log="\n".join(lines),
        template_identity=resolved_template_identity,
    )


def _git_lines(arguments: tuple[str, ...], cwd: Path) -> list[str] | None:
    completed = subprocess.run(
        ("git", *arguments), cwd=cwd, capture_output=True, text=True, errors="replace",
        env=git_environment(), check=False,
    )
    if completed.returncode != 0:
        return None
    return [line for line in completed.stdout.splitlines() if line.strip()]


def changed_since_start(workspace: Path) -> frozenset[str] | None:
    """Workspace-relative paths the builder created or modified since the
    arm's initial commit — committed, staged, unstaged, and untracked alike.

    Returns None when git cannot answer (the caller then treats every file as
    pristine scaffolding, the conservative reading).
    """
    roots = _git_lines(("rev-list", "--max-parents=0", "HEAD"), workspace)
    if not roots:
        return None
    committed = _git_lines(("diff", "--name-only", f"{roots[-1]}..HEAD"), workspace)
    porcelain = _git_lines(("status", "--porcelain", "--untracked-files=all"), workspace)
    if committed is None or porcelain is None:
        return None
    changed: set[str] = set(committed)
    for line in porcelain:
        entry = line[3:] if len(line) > 3 else ""
        # A rename entry reads "old -> new"; the deliverable is the new path.
        changed.add(entry.split(" -> ", 1)[-1].strip('"'))
    return frozenset(path for path in changed if path)
