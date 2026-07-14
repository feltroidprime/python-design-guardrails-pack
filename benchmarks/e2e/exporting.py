"""Provider-neutral benchmark trace payloads and exporter port."""

import base64
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

from benchmarks.e2e.config import ARMS, PHASE_BUILD, BenchmarkConfig, LangfuseSettings
from benchmarks.e2e.judging import DIMENSIONS


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceSpan:
    """One pipeline stage represented inside an arm trace."""

    name: str
    output: object


@dataclass(frozen=True, slots=True, kw_only=True)
class ArmTrace:
    """Complete provider-neutral trace for one benchmark arm and phase."""

    run_id: str
    arm: str
    name: str
    tags: tuple[str, ...]
    metadata: dict[str, object]
    spans: tuple[TraceSpan, ...]
    scores: tuple[tuple[str, float], ...]


class BenchmarkExporter(Protocol):
    """External observability boundary, called only after measurement."""

    def export(self, trace: ArmTrace) -> None: ...


class LangfuseExportError(RuntimeError):
    """Langfuse rejected an ingestion batch."""


class LangfuseExporter:
    """Synchronous adapter for Langfuse's provider-neutral ingestion API."""

    def __init__(
        self,
        *,
        base_url: str,
        public_key: str,
        secret_key: str,
        timeout_seconds: float,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/api/public/ingestion"
        credentials = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
        self._authorization = f"Basic {credentials}"
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(
        cls,
        settings: LangfuseSettings,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "LangfuseExporter":
        environment = os.environ if environ is None else environ
        public_key = environment.get(settings.public_key_env)
        secret_key = environment.get(settings.secret_key_env)
        missing = [
            name
            for name, value in (
                (settings.public_key_env, public_key),
                (settings.secret_key_env, secret_key),
            )
            if not value
        ]
        if missing:
            raise LangfuseExportError("missing credential environment variables: " + ", ".join(missing))
        assert public_key is not None and secret_key is not None
        return cls(
            base_url=settings.base_url,
            public_key=public_key,
            secret_key=secret_key,
            timeout_seconds=settings.timeout_seconds,
        )

    def export(self, trace: ArmTrace) -> None:
        payload = {"batch": _ingestion_events(trace)}
        request = Request(
            self._url,
            data=json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"),
            headers={
                "Authorization": self._authorization,
                "Content-Type": "application/json",
                "User-Agent": "python-design-guardrails-benchmark/1",
            },
            method="POST",
        )
        with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
            body = response.read().decode("utf-8")
        try:
            outcome = json.loads(body)
        except json.JSONDecodeError as error:
            raise LangfuseExportError("ingestion returned invalid JSON") from error
        errors = outcome.get("errors") if isinstance(outcome, dict) else None
        if errors:
            raise LangfuseExportError(f"ingestion rejected events: {errors}")


def langfuse_trace_id(trace: ArmTrace) -> str:
    """Stable Langfuse trace ID, also used by the round-trip integration test."""
    phase = str(trace.metadata.get("phase") or PHASE_BUILD)
    return str(
        uuid5(
            NAMESPACE_URL,
            f"guardrails-benchmark:{trace.run_id}:{phase}:{trace.arm}",
        )
    )


def _event_id(trace_id: str, kind: str, name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{trace_id}:{kind}:{name}"))


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _duration_seconds(output: object) -> float:
    if not isinstance(output, dict):
        return 0.0
    direct = output.get("duration_seconds", output.get("seconds"))
    numeric = _number(direct)
    if numeric is not None:
        return max(0.0, numeric)
    results = output.get("results")
    if isinstance(results, list):
        return sum(
            max(0.0, value)
            for entry in results
            if isinstance(entry, dict)
            if (value := _number(entry.get("duration_seconds"))) is not None
        )
    return 0.0


def _ingestion_events(trace: ArmTrace) -> list[dict[str, object]]:
    trace_id = langfuse_trace_id(trace)
    timestamp = datetime.now(timezone.utc)
    template = _mapping(trace.metadata.get("template"))
    trace_body: dict[str, object] = {
        "id": trace_id,
        "name": trace.name,
        "sessionId": trace.run_id,
        "version": str(template.get("version") or "unknown"),
        "tags": list(trace.tags),
        "metadata": trace.metadata,
    }
    release = trace.metadata.get("pack_revision")
    if release is not None:
        trace_body["release"] = str(release)
    events: list[dict[str, object]] = [
        {
            "id": _event_id(trace_id, "trace-create", trace.name),
            "timestamp": _iso(timestamp),
            "type": "trace-create",
            "body": trace_body,
        }
    ]
    cursor = timestamp
    for span in trace.spans:
        end = cursor + timedelta(seconds=_duration_seconds(span.output))
        events.append(
            {
                "id": _event_id(trace_id, "span-create", span.name),
                "timestamp": _iso(timestamp),
                "type": "span-create",
                "body": {
                    "id": _event_id(trace_id, "span", span.name),
                    "traceId": trace_id,
                    "name": span.name,
                    "startTime": _iso(cursor),
                    "endTime": _iso(end),
                    "output": span.output,
                    "metadata": {"arm": trace.arm, "stage": span.name},
                },
            }
        )
        cursor = end
    for name, value in trace.scores:
        events.append(
            {
                "id": _event_id(trace_id, "score-create", name),
                "timestamp": _iso(timestamp),
                "type": "score-create",
                "body": {
                    "id": _event_id(trace_id, "score", name),
                    "traceId": trace_id,
                    "name": name,
                    "value": value,
                    "dataType": "NUMERIC",
                },
            }
        )
    return events


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _score(scores: list[tuple[str, float]], name: str, value: object) -> None:
    numeric = _number(value)
    if numeric is not None:
        scores.append((name, numeric))


def arm_traces(cfg: BenchmarkConfig, results: dict[str, object]) -> tuple[ArmTrace, ...]:
    """Translate completed results into one trace per arm and scenario phase."""
    meta = _mapping(results.get("meta"))
    template = _mapping(meta.get("template"))
    run_id = str(meta.get("run_id") or cfg.run.label)
    template_version = str(template.get("version") or "unknown")
    variant = str(template.get("variant") or cfg.template.variant)
    pack_revision = meta.get("pack_revision")
    headless_revision = meta.get("headless_llm_revision")

    raw_phases = results.get("phases")
    phases = (
        _mapping(raw_phases)
        if isinstance(raw_phases, dict)
        else {
            PHASE_BUILD: {
                "arms": results.get("arms"),
                "judging": results.get("judging"),
            }
        }
    )
    traces: list[ArmTrace] = []
    for phase, raw_phase_results in phases.items():
        phase_results = _mapping(raw_phase_results)
        arms = _mapping(phase_results.get("arms"))
        judging = _mapping(phase_results.get("judging"))
        aggregate = _mapping(judging.get("aggregate"))
        primary = _mapping(aggregate.get("primary_preferences"))
        dimension_means = _mapping(aggregate.get("dimension_means"))
        for arm in ARMS:
            arm_results = _mapping(arms.get(arm))
            agent = _mapping(arm_results.get("agent") or arm_results.get("build"))
            probes = _mapping(arm_results.get("probes"))
            metrics = _mapping(arm_results.get("metrics"))
            arm_dimensions = _mapping(dimension_means.get(arm))
            analyzer_output = {
                name: metrics[name]
                for name in ("loc", "coverage", "ruff", "basedpyright", "radon")
                if name in metrics
            }
            judging_output = {
                "primary_preference": primary.get(arm),
                "dimensions": arm_dimensions,
            }
            scores: list[tuple[str, float]] = []
            _score(scores, "probe_pass_rate", probes.get("pass_rate"))
            _score(scores, "judge_primary_preference", primary.get(arm))
            for dimension in DIMENSIONS:
                _score(scores, f"judge_{dimension}", arm_dimensions.get(dimension))
            _score(
                scores,
                "ruff_violations_per_kloc",
                _mapping(metrics.get("ruff")).get("per_kloc"),
            )
            _score(
                scores,
                "basedpyright_errors_per_kloc",
                _mapping(metrics.get("basedpyright")).get("errors_per_kloc"),
            )
            _score(
                scores,
                "coverage_percent",
                _mapping(metrics.get("coverage")).get("percent"),
            )
            _score(scores, "wall_time_seconds", agent.get("duration_seconds"))
            _score(scores, "cost_usd", agent.get("cost_usd"))
            token_values: list[float] = []
            for result_key, score_name in (
                ("input_tokens", "input_tokens"),
                ("output_tokens", "output_tokens"),
                ("reasoning_tokens", "reasoning_tokens"),
                ("cached_input_tokens", "cached_input_tokens"),
            ):
                value = _number(agent.get(result_key))
                if value is not None:
                    scores.append((score_name, value))
                    if result_key != "cached_input_tokens":
                        token_values.append(value)
            if token_values:
                scores.append(("total_tokens", sum(token_values)))
            _score(scores, "tool_calls", agent.get("tool_calls"))
            _score(scores, "turns", agent.get("turns"))

            metadata = {
                "arm": arm,
                "template": dict(template),
                "app": cfg.project.name,
                "phase": phase,
                "provider": cfg.builder.provider,
                "model": cfg.builder.model,
                "effort": cfg.builder.effort,
                "seed": cfg.run.seed,
                "run_label": cfg.run.label,
                "pack_revision": pack_revision,
                "headless_llm_revision": headless_revision,
            }
            tags = (
                f"arm:{arm}",
                f"template:{template_version}",
                f"variant:{variant}",
                f"app:{cfg.project.name}",
                f"phase:{phase}",
                f"provider:{cfg.builder.provider}",
                f"model:{cfg.builder.model or 'default'}",
                f"effort:{cfg.builder.effort or 'default'}",
                f"seed:{cfg.run.seed}",
                f"run:{cfg.run.label}",
                f"pack:{pack_revision or 'unknown'}",
                f"headless_llm:{headless_revision or 'unknown'}",
            )
            trace_name = f"benchmark:{cfg.project.name}:{arm}"
            if phase != PHASE_BUILD:
                trace_name = f"benchmark:{cfg.project.name}:{phase}:{arm}"
            traces.append(
                ArmTrace(
                    run_id=run_id,
                    arm=arm,
                    name=trace_name,
                    tags=tags,
                    metadata=metadata,
                    spans=(
                        TraceSpan(name="instantiate", output=arm_results.get("setup", {})),
                        TraceSpan(
                            name="build" if phase == PHASE_BUILD else "change",
                            output=agent,
                        ),
                        TraceSpan(name="install", output=metrics.get("install", {})),
                        TraceSpan(name="self-tests", output=metrics.get("own_tests", {})),
                        TraceSpan(name="probes", output=probes),
                        TraceSpan(name="analyzers", output=analyzer_output),
                        TraceSpan(name="judging", output=judging_output),
                    ),
                    scores=tuple(scores),
                )
            )
    return tuple(traces)
