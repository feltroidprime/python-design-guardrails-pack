"""The only module that touches headless_llm, and only lazily.

Everything else depends on the `AgentRunner` protocol, so the deterministic
test suite exercises the full pipeline with fakes and never needs the
provider SDKs installed.
"""

from dataclasses import dataclass
from typing import Protocol

from benchmarks.e2e.config import BuilderSettings, RoleSettings


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentOutcome:
    """Provider-neutral result of one agent run, ready for JSON serialization."""

    text: str
    structured: object | None
    model: str | None
    duration_ms: int
    turns: int | None
    tool_calls: int
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None
    cost_usd: float | None
    cost_provenance: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "duration_ms": self.duration_ms,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cost_usd": self.cost_usd,
            "cost_provenance": self.cost_provenance,
            "text": self.text,
        }


class AgentRunner(Protocol):
    """One configured LLM role that can execute a prompt and report stats."""

    def run(
        self,
        prompt: str,
        *,
        working_directory: str | None = None,
        timeout_seconds: float,
        output_schema: dict[str, object] | None = None,
    ) -> AgentOutcome: ...


class RunnerFactory(Protocol):
    def __call__(self, role: RoleSettings) -> AgentRunner: ...


class _HeadlessRunner:
    def __init__(self, role: RoleSettings) -> None:
        from headless_llm import create_client

        self._role = role
        self._client = create_client(
            role.provider,
            model=role.model,
            effort=role.effort,
            binary=role.binary,
        )

    def run(
        self,
        prompt: str,
        *,
        working_directory: str | None = None,
        timeout_seconds: float,
        output_schema: dict[str, object] | None = None,
    ) -> AgentOutcome:
        from headless_llm import RunOptions

        allowed_tools: tuple[str, ...] | None = None
        if isinstance(self._role, BuilderSettings):
            allowed_tools = self._role.allowed_tools
        elif output_schema is not None and self._role.provider in ("claude", "opencode"):
            # Judges receive the full bundle inline; tool use would only let
            # provider-specific browsing skew (and unblind) an otherwise
            # identical protocol. Codex exposes no per-run allow-list, so its
            # judges rely on the neutral empty working directory instead.
            allowed_tools = ()
        result = self._client.run(
            prompt,
            options=RunOptions(
                working_directory=working_directory,
                timeout_seconds=timeout_seconds,
                output_schema=output_schema,
                allowed_tools=allowed_tools,
                # An explicit empty tuple opts out of whatever MCP servers the
                # host machine has configured globally: benchmark agents must
                # not inherit machine-specific capabilities or their context
                # cost, or the run stops being reproducible elsewhere.
                mcp_servers=(),
            ),
        )
        usage = result.stats.usage
        return AgentOutcome(
            text=result.text,
            structured=result.structured_output,
            model=result.model,
            duration_ms=result.stats.duration_ms,
            turns=result.stats.turns,
            tool_calls=result.stats.tool_count,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            cost_usd=usage.cost_usd,
            cost_provenance=(
                usage.cost_provenance.value if usage.cost_provenance is not None else None
            ),
        )


def create_runner(role: RoleSettings) -> AgentRunner:
    """Build a real headless_llm-backed runner. Imports the SDK lazily."""
    return _HeadlessRunner(role)
