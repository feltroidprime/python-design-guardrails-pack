"""The five commands of steps 7 to 9: `git init`, the first commit, `just
setup`, `prek install`, and `gh repo create`.

The order is fixed: `git init`, then the first commit, then `just setup`. The
commit must exist before `just setup` runs. `just setup` runs the gate, and
the gate reads the tracked tree through `git ls-files`. A repository with no
commit has no tracked file. The gate then fails on a fact that is true by
construction, not a defect of the tree. `prek install` runs again after `just
setup`, because it is its own step, and rewiring the same managed hook is
idempotent.

`gh repo create` is the one command that reaches the network, and only
`--github` selects it. Every command here comes from the port, so a test drives
this order with a stub on `PATH` and never opens a socket.
"""

from pathlib import Path

from guardrails_pack.bootstrap.application.ports import CommandRunner
from guardrails_pack.bootstrap.domain.identity import Identity

__all__ = ["prepare_repository", "publish"]

GATE_CONFIG = "pack/configs/prek.toml"
SETUP_RECIPE = "setup"
FALLBACK_NAME = "Terminal Project"
FALLBACK_EMAIL = "project@localhost"


def _identity_arguments(runner: CommandRunner, directory: Path) -> tuple[str, ...]:
    """A one-time git identity, and only when the machine states none."""
    if runner.succeeds(("git", "config", "--get", "user.email"), directory):
        return ()
    return ("-c", f"user.name={FALLBACK_NAME}", "-c", f"user.email={FALLBACK_EMAIL}")


def prepare_repository(runner: CommandRunner, directory: Path, project: Identity) -> None:
    """Steps 7 and 8: the repository, its first commit, its dependencies, its hooks."""
    runner.run(("git", "init", "--quiet", "--initial-branch=main"), directory)
    identity = _identity_arguments(runner, directory)
    message = f"Initial commit of {project.project_name}"
    runner.run(("git", "add", "--all"), directory)
    runner.run(("git", *identity, "commit", "--quiet", "--message", message), directory)
    runner.run(("just", SETUP_RECIPE), directory)
    runner.run(("uv", "run", "prek", "install", "-f", "-c", GATE_CONFIG), directory)


def publish(runner: CommandRunner, directory: Path, project: Identity, *, public: bool) -> None:
    """Step 9: create the GitHub repository and push. This is the one network step."""
    visibility = "--public" if public else "--private"
    runner.run(
        (
            "gh",
            "repo",
            "create",
            project.project_name,
            visibility,
            "--source",
            ".",
            "--remote",
            "origin",
            "--push",
        ),
        directory,
    )
