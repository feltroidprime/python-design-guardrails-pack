"""Structured progress events emitted by the orchestrator.

The plain log remains the source of truth for headless runs; events exist so
a live front-end (the rich TUI) can render both arms concurrently without
parsing log lines. Standard library only — consumers decide how to draw.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

RUN_STARTED = "run_started"
ARM_STAGE = "arm_stage"
BUILD_FINISHED = "build_finished"
PROBE_RESULT = "probe_result"
METRICS_READY = "metrics_ready"
GATE_RESULT = "gate_result"
JUDGING_STARTED = "judging_started"
JUDGMENT = "judgment"
JUDGE_FAILED = "judge_failed"
RUN_FINISHED = "run_finished"

STAGE_WORKSPACE = "workspace"
STAGE_BUILDING = "building"
STAGE_PROBES = "probes"
STAGE_METRICS = "metrics"
STAGE_GATE = "gate"
STAGE_DONE = "done"

ARM_STAGES = (
    STAGE_WORKSPACE,
    STAGE_BUILDING,
    STAGE_PROBES,
    STAGE_METRICS,
    STAGE_GATE,
    STAGE_DONE,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    kind: str
    arm: str | None = None
    payload: dict[str, object] = field(default_factory=dict)


EventSink = Callable[[Event], None]


def ignore_event(_event: Event) -> None:
    return None
