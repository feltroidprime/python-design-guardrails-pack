from pathlib import Path
import random

import pytest

from scripts.agent_sessions import AgentType, convert_session
from tests.e2e.session_contract import assert_valid_bundle

QUANTILE_COUNT = 5


def _candidates(agent_type: AgentType) -> list[Path]:
    root = (
        Path.home() / ".codex" / "sessions"
        if agent_type == "codex"
        else Path.home() / ".claude" / "projects"
    )
    if not root.is_dir():
        return []
    candidates = [
        path
        for path in root.rglob("*.jsonl")
        if path.is_file() and (agent_type != "claude" or "subagents" not in path.parts)
    ]
    return sorted(candidates, key=lambda path: (path.stat().st_size, path.as_posix()))


def _size_quantile_sample(candidates: list[Path]) -> list[Path]:
    chooser = random.SystemRandom()
    return [
        chooser.choice(
            candidates[
                len(candidates) * band // QUANTILE_COUNT : len(candidates)
                * (band + 1)
                // QUANTILE_COUNT
            ]
        )
        for band in range(QUANTILE_COUNT)
    ]


@pytest.mark.session_e2e
@pytest.mark.parametrize("agent_type", ["claude", "codex"])
def test_random_real_sessions_across_size_quantiles(
    agent_type: AgentType,
    tmp_path: Path,
) -> None:
    candidates = _candidates(agent_type)
    if not candidates:
        pytest.skip(f"No local {agent_type} sessions are available")
    if len(candidates) < QUANTILE_COUNT:
        requirement = f"Five size quantiles require {QUANTILE_COUNT} local {agent_type} sessions"
        pytest.fail(f"{requirement}; found {len(candidates)}.")
    for band, source in enumerate(_size_quantile_sample(candidates), 1):
        output = tmp_path / f"{agent_type}-q{band}"
        _ = convert_session(source, output)
        _ = assert_valid_bundle(output, agent_type=agent_type)
