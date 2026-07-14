"""Deterministic cross-run report tests: no provider SDK and no network."""

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_COMMAND = REPO_ROOT / "benchmarks" / "report.py"


def _row(
    *,
    version: str,
    variant: str,
    app: str,
    phase: str,
    provider: str,
    model: str,
    arm: str,
    probe: float,
    wall_time: float,
    cost: float,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": f"{app}-{model}-{arm}",
        "started_utc": "2026-07-14T10:00:00+00:00",
        "run_label": app,
        "arm": arm,
        "template": {
            "version": version,
            "vcs_ref": version,
            "variant": variant,
            "answers": {"project_name": app, "package": app},
        },
        "variant": variant,
        "app": app,
        "phase": phase,
        "provider": provider,
        "model": model,
        "effort": "high",
        "seed": 3,
        "pack_revision": "abc1234",
        "headless_llm_revision": "def5678",
        "probe_pass_rate": probe,
        "judge_primary_votes": 1 if arm == "guardrails" else 0,
        "judge_dimension_means": {
            "spec_fidelity": 8.0 if arm == "guardrails" else 6.0,
            "test_quality": 7.0 if arm == "guardrails" else 5.0,
        },
        "analyzer_densities": {
            "ruff_violations_per_kloc": 1.0,
            "basedpyright_errors_per_kloc": 0.5,
        },
        "coverage_percent": 91.0 if arm == "guardrails" else 72.0,
        "wall_time_seconds": wall_time,
        "cost_usd": cost,
        "input_tokens": 1000,
        "cached_input_tokens": 250,
        "output_tokens": 500,
        "reasoning_tokens": 125,
        "tool_calls": 40,
        "turns": 12,
    }


def test_report_cli_renders_grouped_offline_comparisons(tmp_path: Path) -> None:
    registry = REPO_ROOT / "tests" / "fixtures" / "benchmark_registry.jsonl"
    output = tmp_path / "bench-report.html"

    completed = subprocess.run(
        (
            sys.executable,
            str(REPORT_COMMAND),
            "--registry",
            str(registry),
            "--output",
            str(output),
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Wrote cross-run benchmark report" in completed.stdout
    html = output.read_text(encoding="utf-8")
    for expected in (
        "Benchmark Lab — cross-run comparison",
        "Template version",
        "Model",
        "Application",
        "Variant",
        "Phase",
        "v1.0.0",
        "v1.1.0-dirty",
        "claude-opus-4-8",
        "gpt-5.6-tera",
        "ledger",
        "relay",
        "checks-via-commit",
        "maintenance",
        "Quality vs wall-clock",
        "Quality vs dollars",
        "Effort metrics",
        "Probe pass rate",
        "Judge dimension mean",
        "Cached input tokens",
    ):
        assert expected in html
    assert 'data-template-version="v1.0.0"' in html
    assert 'data-template-version="v1.1.0-dirty"' in html
    assert "<style>" in html and "<script>" in html
    assert "<script src=" not in html
    assert "<link " not in html
    assert 'src="http' not in html
    assert 'href="http' not in html


def test_report_cli_handles_empty_or_missing_registry_without_traceback(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.touch()
    for registry in (tmp_path / "missing.jsonl", empty):
        output = tmp_path / f"{registry.stem}.html"
        completed = subprocess.run(
            (
                sys.executable,
                str(REPORT_COMMAND),
                "--registry",
                str(registry),
                "--output",
                str(output),
            ),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0
        assert "No benchmark runs found" in completed.stdout
        assert "Traceback" not in completed.stderr
        assert not output.exists()


def test_registry_and_report_import_without_provider_sdk() -> None:
    completed = subprocess.run(
        (
            sys.executable,
            "-c",
            "import benchmarks.e2e.registry; import benchmarks.report; "
            "import sys; assert 'headless_llm' not in sys.modules",
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_just_bench_report_renders_fixture_registry(tmp_path: Path) -> None:
    registry = tmp_path / "registry.jsonl"
    registry.write_text(
        json.dumps(
            _row(
                version="v1.2.0",
                variant="baseline",
                app="ledger",
                phase="build",
                provider="claude",
                model="claude-opus-4-8",
                arm="guardrails",
                probe=1.0,
                wall_time=700.0,
                cost=3.2,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "from-just.html"

    completed = subprocess.run(
        ("just", "bench-report", str(registry), str(output)),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
    assert "v1.2.0" in output.read_text(encoding="utf-8")
    assert "just bench-report" in (REPO_ROOT / "benchmarks" / "README.md").read_text(
        encoding="utf-8"
    )
