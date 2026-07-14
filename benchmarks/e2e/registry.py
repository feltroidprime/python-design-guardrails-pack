"""Append-only cross-run benchmark summaries.

This module deliberately depends only on the harness's typed configuration
and completed result dictionaries. Provider clients remain isolated in
``agents.py`` and are never needed to record or report existing runs.
"""

from collections.abc import Iterable
import json
from pathlib import Path

from benchmarks.e2e.config import ARMS, BenchmarkConfig

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
    aggregate = _get(results, "judging", "aggregate")
    primary = (
        aggregate.get("primary_preferences") if isinstance(aggregate, dict) else None
    )
    dimensions = (
        aggregate.get("dimension_means") if isinstance(aggregate, dict) else None
    )

    rows: list[dict[str, object]] = []
    for arm in ARMS:
        build = _get(results, "arms", arm, "build")
        build = build if isinstance(build, dict) else {}
        arm_dimensions = dimensions.get(arm) if isinstance(dimensions, dict) else None
        rows.append(
            {
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
                "phase": "build",
                "provider": cfg.builder.provider,
                "model": build.get("model") or cfg.builder.model or "default",
                "effort": cfg.builder.effort,
                "seed": meta.get("seed"),
                "pack_revision": meta.get("pack_revision"),
                "headless_llm_revision": meta.get("headless_llm_revision"),
                "probe_pass_rate": _get(results, "arms", arm, "probes", "pass_rate"),
                "judge_primary_votes": (
                    primary.get(arm) if isinstance(primary, dict) else None
                ),
                "judge_dimension_means": (
                    dict(arm_dimensions) if isinstance(arm_dimensions, dict) else {}
                ),
                "analyzer_densities": {
                    "ruff_violations_per_kloc": _get(
                        results, "arms", arm, "metrics", "ruff", "per_kloc"
                    ),
                    "basedpyright_errors_per_kloc": _get(
                        results,
                        "arms",
                        arm,
                        "metrics",
                        "basedpyright",
                        "errors_per_kloc",
                    ),
                },
                "coverage_percent": _get(
                    results, "arms", arm, "metrics", "coverage", "percent"
                ),
                "wall_time_seconds": build.get("duration_seconds"),
                "cost_usd": build.get("cost_usd"),
                "input_tokens": build.get("input_tokens"),
                "cached_input_tokens": build.get("cached_input_tokens"),
                "output_tokens": build.get("output_tokens"),
                "reasoning_tokens": build.get("reasoning_tokens"),
                "tool_calls": build.get("tool_calls"),
                "turns": build.get("turns"),
            }
        )
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
