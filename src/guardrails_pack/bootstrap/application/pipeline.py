"""The five commands that turn a projected tree into a working repository.

The order is fixed: `git init`, `just setup`, the first commit, then
`prek install`. `just setup` installs the dependencies, installs the git hooks,
and runs the gate, so the tree is proved before it is committed. `prek install`
runs again after the commit, because #85 section 3.3 states it as its own step
and rewiring the same managed hook is idempotent.

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
    """Steps 5 and 6: the repository, its dependencies, its first commit, its hooks."""
    runner.run(("git", "init", "--quiet", "--initial-branch=main"), directory)
    runner.run(("just", SETUP_RECIPE), directory)
    identity = _identity_arguments(runner, directory)
    message = f"Initial commit of {project.project_name}"
    runner.run(("git", "add", "--all"), directory)
    runner.run(("git", *identity, "commit", "--quiet", "--message", message), directory)
    runner.run(("uv", "run", "prek", "install", "-f", "-c", GATE_CONFIG), directory)


def publish(runner: CommandRunner, directory: Path, project: Identity, *, public: bool) -> None:
    """Step 7: create the GitHub repository and push. This is the one network step."""
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
