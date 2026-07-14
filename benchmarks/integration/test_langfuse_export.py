"""Opt-in round trip against the pinned local Langfuse stack.

Excluded from ``just test`` because that command collects only ``tests/``.
"""

import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

from benchmarks.e2e.agents import AgentOutcome
from benchmarks.e2e.config import (
    ARM_BARE,
    BenchmarkConfig,
    BuilderSettings,
    JudgeSettings,
    LangfuseSettings,
    ProbeSpec,
    ProjectSettings,
    RoleSettings,
    RunSettings,
    TemplateSettings,
    ToolPins,
)
from benchmarks.e2e.exporting import LangfuseExporter, arm_traces, langfuse_trace_id
from benchmarks.e2e.judging import DIMENSIONS
from benchmarks.e2e.orchestrator import run_benchmark

REPO_ROOT = Path(__file__).resolve().parents[2]
ENABLED = os.environ.get("LANGFUSE_INTEGRATION") == "1"


def _local_environment() -> dict[str, str]:
    values = dict(os.environ)
    env_file = REPO_ROOT / "benchmarks" / "langfuse" / ".env"
    if env_file.is_file():
        values.update(
            line.split("=", 1)
            for line in env_file.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        )
    return values


@dataclass
class _FakeRunner:
    def run(
        self,
        prompt: str,
        *,
        working_directory: str | None = None,
        timeout_seconds: float,
        output_schema: dict[str, object] | None = None,
    ) -> AgentOutcome:
        del prompt, timeout_seconds
        structured = None
        if output_schema is None:
            assert working_directory is not None
            (Path(working_directory) / "built_by_fake.py").write_text("answer = 42\n", encoding="utf-8")
        else:
            scores = {dimension: 7 for dimension in DIMENSIONS}
            structured = {
                "candidate_a": {**scores, "top_risk": "risk a"},
                "candidate_b": {**scores, "top_risk": "risk b"},
                "preference": "a",
                "preference_strength": "slight",
                "rationale": "integration fixture",
            }
        return AgentOutcome(
            text="fake",
            structured=structured,
            model="fake-model",
            duration_ms=10,
            turns=1,
            tool_calls=1,
            input_tokens=10,
            output_tokens=5,
            reasoning_tokens=0,
            cached_input_tokens=0,
            cost_usd=0.001,
            cost_provenance="computed",
        )


def _config(tmp_path: Path, settings: LangfuseSettings) -> BenchmarkConfig:
    source = tmp_path / "config.toml"
    source.write_text("# integration fixture\n", encoding="utf-8")
    return BenchmarkConfig(
        source_path=source,
        run=RunSettings(
            output_root=tmp_path / "runs",
            label="langfuse-integration",
            seed=17,
            run_native_gate=False,
            parallel_arms=False,
        ),
        project=ProjectSettings(name="langfuse-demo", package="langfuse_demo"),
        template=TemplateSettings(answers={}),
        builder=BuilderSettings(provider="claude", model="fake-model"),
        judge=JudgeSettings(panel=(RoleSettings(provider="codex"),)),
        probes=(
            ProbeSpec(
                name="fake-build-marker",
                argv=(sys.executable, "{ws}/built_by_fake.py"),
            ),
        ),
        tools=ToolPins(ruff="1", basedpyright="1", radon="1", coverage="1"),
        spec_text="fake integration specification " * 20,
        charter_text="fake integration charter",
        langfuse=settings,
    )


def _read_trace(*, base_url: str, trace_id: str, public_key: str, secret_key: str) -> dict[str, object]:
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
    request = Request(
        f"{base_url.rstrip('/')}/api/public/traces/{trace_id}",
        headers={"Authorization": f"Basic {credentials}"},
    )
    deadline = time.monotonic() + 30
    while True:
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310
                return json.loads(response.read())
        except HTTPError, URLError, ConnectionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)


@pytest.mark.skipif(not ENABLED, reason="set LANGFUSE_INTEGRATION=1 for local stack")
def test_fake_agent_run_round_trips_through_local_langfuse(tmp_path: Path) -> None:
    environment = _local_environment()
    settings = LangfuseSettings(
        enabled=True,
        base_url=environment.get("LANGFUSE_BASE_URL", "http://127.0.0.1:3000"),
    )
    exporter = LangfuseExporter.from_settings(settings, environ=environment)
    cfg = _config(tmp_path, settings)

    run = run_benchmark(
        cfg,
        repo_root=REPO_ROOT,
        runner_factory=lambda role: _FakeRunner(),
        metrics_collector=lambda workspace, out_dir: {
            "coverage": {"percent": 100.0},
            "ruff": {"per_kloc": 0.0},
            "basedpyright": {"errors_per_kloc": 0.0},
        },
        exporter=exporter,
        log=lambda message: None,
    )

    trace = arm_traces(cfg, run.results)[0]
    assert trace.arm == ARM_BARE
    received = _read_trace(
        base_url=settings.base_url,
        trace_id=langfuse_trace_id(trace),
        public_key=environment[settings.public_key_env],
        secret_key=environment[settings.secret_key_env],
    )
    assert received["id"] == langfuse_trace_id(trace)
    assert received["name"] == "benchmark:langfuse-demo:bare"
    assert set(trace.tags).issubset(received["tags"])
