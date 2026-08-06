"""Lazy compatibility facade over the commit-pinned private session profiler."""

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
