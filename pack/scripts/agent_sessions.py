"""Lazy loader for `session-profiler-optimizer`, an opt-in private dependency.

`pack/justfile`'s `session-log` and `session-e2e` recipes install this
distribution just for that one run, through `uv run --with`. No other
recipe depends on it, and `uv sync` never installs it. The import stays
inside `convert_session` so every other command can run without it.

Call `convert_session` only through `just session-log` or `just
session-e2e`. Anywhere else, the import raises `ModuleNotFoundError`. Run
one of those two recipes instead of importing this module directly.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Literal, Protocol, cast

if TYPE_CHECKING:
    from pathlib import Path

type AgentType = Literal["auto", "claude", "codex"]


class _ConvertSession(Protocol):
    def __call__(
        self,
        input_path: Path,
        output_dir: Path,
        agent_type: AgentType = "auto",
    ) -> Path: ...


def convert_session(
    input_path: Path,
    output_dir: Path,
    agent_type: AgentType = "auto",
) -> Path:
    """Load the opt-in dependency only when session evidence is requested."""
    package = import_module("session_profiler_optimizer")
    raw_converter = vars(package).get("convert_session")
    if not callable(raw_converter):
        raise TypeError("session-profiler-optimizer has no convert_session entry point.")
    return cast("_ConvertSession", raw_converter)(input_path, output_dir, agent_type)


__all__ = ["AgentType", "convert_session"]
