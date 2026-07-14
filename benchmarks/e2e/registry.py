"""Append-only cross-run benchmark summaries.

This module deliberately depends only on the harness's typed configuration
and completed result dictionaries. Provider clients remain isolated in
``agents.py`` and are never needed to record or report existing runs.
"""

from collections.abc import Iterable
import json
from pathlib import Path

from benchmarks.e2e.config import ARMS, PHASE_BUILD, BenchmarkConfig

REGISTRY_FILENAME = "registry.jsonl"


def _get(mapping: object, *keys: str) -> object:
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def registry_rows(
    results: dict[str, object], cfg: BenchmarkConfig
) -> list[dict[str, object]]:
    """Return one publication-oriented summary row for each benchmark arm."""
    meta = results.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("completed benchmark results have no meta section")
    template = meta.get("template")
    if not isinstance(template, dict):
        raise ValueError("completed benchmark manifest has no Copier template identity")
    variant = template.get("variant")
    raw_phases = results.get("phases")
    phases = (
        raw_phases
        if isinstance(raw_phases, dict)
        else {
            PHASE_BUILD: {
                "arms": results.get("arms"),
                "judging": results.get("judging"),
            }
        }
    )

    rows: list[dict[str, object]] = []
    for phase, phase_results in phases.items():
        if not isinstance(phase_results, dict):
            raise ValueError(f"completed benchmark phase {phase!r} is not an object")
        aggregate = _get(phase_results, "judging", "aggregate")
        primary = (
            aggregate.get("primary_preferences") if isinstance(aggregate, dict) else None
        )
        dimensions = (
            aggregate.get("dimension_means") if isinstance(aggregate, dict) else None
        )
        for arm in ARMS:
            agent = _get(phase_results, "arms", arm, "agent")
            if not isinstance(agent, dict):
                agent = _get(phase_results, "arms", arm, "build")
            agent = agent if isinstance(agent, dict) else {}
            arm_dimensions = dimensions.get(arm) if isinstance(dimensions, dict) else None
            rows.append({
                "schema_version": 1,
                "run_id": meta.get("run_id"),
                "started_utc": meta.get("started_utc"),
                "run_label": cfg.run.label,
                "arm": arm,
                # This is copied verbatim from the manifest. In particular,
                # the resolved Copier version is never re-derived here.
                "template": dict(template),
                "variant": variant,
                "app": cfg.project.name,
                "phase": phase,
                "provider": cfg.builder.provider,
                "model": agent.get("model") or cfg.builder.model or "default",
                "effort": cfg.builder.effort,
                "seed": meta.get("seed"),
                "pack_revision": meta.get("pack_revision"),
                "headless_llm_revision": meta.get("headless_llm_revision"),
                "probe_pass_rate": _get(
                    phase_results, "arms", arm, "probes", "pass_rate"
                ),
                # The complete primary endpoint is repeated per arm so ties
                # and the eligible-judge denominator are never lost.
                "judge_primary_endpoint": (
                    dict(primary) if isinstance(primary, dict) else {}
                ),
                "judge_dimension_means": (
                    dict(arm_dimensions) if isinstance(arm_dimensions, dict) else {}
                ),
                "analyzer_densities": {
                    "ruff_violations_per_kloc": _get(
                        phase_results, "arms", arm, "metrics", "ruff", "per_kloc"
                    ),
                    "basedpyright_errors_per_kloc": _get(
                        phase_results,
                        "arms",
                        arm,
                        "metrics",
                        "basedpyright",
                        "errors_per_kloc",
                    ),
                },
                "coverage_percent": _get(
                    phase_results, "arms", arm, "metrics", "coverage", "percent"
                ),
                "wall_time_seconds": agent.get("duration_seconds"),
                "cost_usd": agent.get("cost_usd"),
                "input_tokens": agent.get("input_tokens"),
                "cached_input_tokens": agent.get("cached_input_tokens"),
                "output_tokens": agent.get("output_tokens"),
                "reasoning_tokens": agent.get("reasoning_tokens"),
                "tool_calls": agent.get("tool_calls"),
                "turns": agent.get("turns"),
            })
    return rows


def append_registry_rows(path: Path, rows: Iterable[dict[str, object]]) -> None:
    """Append complete JSONL rows without reading or rewriting prior runs."""
    serialized = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), default=str) + "\n"
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as registry:
        registry.write(serialized)
