"""Benchmark orchestration: workspaces → builds → probes → metrics → judging → report.

Fairness invariants owned here:

- `compose_build_prompt` takes no arm parameter, so the two arms cannot
  receive different instructions by construction;
- both arms run through identically configured builder runners, the same
  probe scenario, and the same metric collector;
- the arms are independent until judging and run concurrently by default
  (`run.parallel_arms`), one runner per arm so no client state is shared;
- every stage failure is recorded and reported instead of aborting the run,
  so a broken arm shows up as data, not as a silently missing comparison.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import threading

from benchmarks.e2e.agents import AgentRunner, RunnerFactory
from benchmarks.e2e.config import ARMS, BenchmarkConfig
from benchmarks.e2e import events as ev
from benchmarks.e2e.judging import (
    Bundle,
    aggregate_judgments,
    bundle_workspace,
    run_panel,
)
from benchmarks.e2e.metrics import collect_metrics, run_native_gate
from benchmarks.e2e.probes import pass_rate, run_probes
from benchmarks.e2e.reporting import render_report
from benchmarks.e2e.workspaces import Workspace, changed_since_start, prepare_workspace

MetricsCollector = Callable[[Path, Path], dict[str, object]]
GateRunner = Callable[[Path, Path], dict[str, object]]
Logger = Callable[[str], None]


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkRun:
    run_dir: Path
    results: dict[str, object]


def compose_build_prompt(charter_text: str, spec_text: str) -> str:
    """The single build prompt. By design there is no per-arm variant."""
    return f"{charter_text.strip()}\n\n{spec_text.strip()}\n"


def _git_revision(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ("git", "-C", str(path), "rev-parse", "--short", "HEAD"),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout.strip() or None if completed.returncode == 0 else None


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _git_dirty(path: Path) -> bool | None:
    try:
        completed = subprocess.run(
            ("git", "-C", str(path), "status", "--porcelain"),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return bool(completed.stdout.strip()) if completed.returncode == 0 else None


def _uv_version() -> str | None:
    try:
        completed = subprocess.run(
            ("uv", "--version"), capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return completed.stdout.strip() or None if completed.returncode == 0 else None


def _manifest(cfg: BenchmarkConfig, run_id: str, started: str, repo_root: Path) -> dict[str, object]:
    return {
        "run_id": run_id,
        "started_utc": started,
        "config_path": str(cfg.source_path),
        "seed": cfg.run.seed,
        "builder": cfg.builder.identity,
        "builder_effort": cfg.builder.effort,
        "judges": [member.identity for member in cfg.judge.panel],
        "tool_pins": {
            "ruff": cfg.tools.ruff,
            "basedpyright": cfg.tools.basedpyright,
            "radon": cfg.tools.radon,
            "coverage": cfg.tools.coverage,
        },
        "pack_revision": _git_revision(repo_root),
        "pack_tree_dirty": _git_dirty(repo_root),
        "headless_llm_revision": _git_revision(cfg.run.headless_llm_path),
        "headless_llm_tree_dirty": _git_dirty(cfg.run.headless_llm_path),
        "uv_version": _uv_version(),
        "platform": f"{platform.system()} {platform.release()} / {platform.python_version()}",
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class _ArmOutcome:
    results: dict[str, object]
    bundle: Bundle


def _build_arm(
    arm: str,
    *,
    cfg: BenchmarkConfig,
    prompt: str,
    builder: AgentRunner,
    workspace: Workspace,
    arm_dir: Path,
    log: Logger,
    events: ev.EventSink,
) -> dict[str, object]:
    log(f"[{arm}] building with {cfg.builder.identity} "
        f"(timeout {cfg.builder.timeout_seconds:g}s)")
    try:
        outcome = builder.run(
            prompt,
            working_directory=str(workspace.path),
            timeout_seconds=cfg.builder.timeout_seconds,
        )
    except Exception as error:  # noqa: BLE001 - the run must record, not crash
        log(f"[{arm}] build FAILED: {type(error).__name__}: {error}")
        record: dict[str, object] = {"error": f"{type(error).__name__}: {error}"}
        events(ev.Event(kind=ev.BUILD_FINISHED, arm=arm, payload=dict(record)))
        return record
    (arm_dir / "build_answer.md").write_text(outcome.text, encoding="utf-8")
    record = outcome.as_dict()
    record["duration_seconds"] = round(outcome.duration_ms / 1000, 1)
    record["error"] = None
    del record["text"]
    log(
        f"[{arm}] build finished in {record['duration_seconds']}s, "
        f"{outcome.tool_calls} tool calls, cost {outcome.cost_usd} "
        f"({outcome.cost_provenance or 'unavailable'})"
    )
    events(ev.Event(kind=ev.BUILD_FINISHED, arm=arm, payload=dict(record)))
    return record


def run_benchmark(
    cfg: BenchmarkConfig,
    *,
    repo_root: Path,
    runner_factory: RunnerFactory,
    metrics_collector: MetricsCollector | None = None,
    gate_runner: GateRunner | None = None,
    log: Logger = print,
    events: ev.EventSink = ev.ignore_event,
) -> BenchmarkRun:
    log_lock = threading.Lock()

    def emit(message: str) -> None:
        with log_lock:
            log(message)

    def emit_event(event: ev.Event) -> None:
        with log_lock:
            events(event)

    started_at = datetime.now(timezone.utc)
    run_id = f"{cfg.run.label}-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = cfg.run.output_root / run_id
    arms_dir = run_dir / "arms"
    run_dir.mkdir(parents=True, exist_ok=False)

    collect = metrics_collector or (
        lambda workspace, out_dir: collect_metrics(
            workspace, out_dir, pins=cfg.tools, run=cfg.run, app_exclude=cfg.judge.exclude
        )
    )
    gate = gate_runner or (lambda workspace, out_dir: run_native_gate(workspace, out_dir, run=cfg.run))

    shutil.copy2(cfg.source_path, run_dir / "config.toml")
    prompt = compose_build_prompt(cfg.charter_text, cfg.spec_text)
    (run_dir / "build_prompt.md").write_text(prompt, encoding="utf-8")

    manifest = _manifest(cfg, run_id, started_at.isoformat(), repo_root)
    _write_json(run_dir / "manifest.json", manifest)
    emit(f"run directory: {run_dir}")
    emit_event(
        ev.Event(
            kind=ev.RUN_STARTED,
            payload={
                "run_id": run_id,
                "builder": cfg.builder.identity,
                "judges": [member.identity for member in cfg.judge.panel],
                "probe_names": [probe.name for probe in cfg.probes],
                "run_dir": str(run_dir),
            },
        )
    )

    def stage(arm: str, name: str) -> None:
        emit_event(ev.Event(kind=ev.ARM_STAGE, arm=arm, payload={"stage": name}))

    def run_arm(arm: str) -> _ArmOutcome:
        arm_dir = arms_dir / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        stage(arm, ev.STAGE_WORKSPACE)
        workspace = prepare_workspace(arm, cfg, arms_dir, repo_root=repo_root)
        emit(f"[{arm}] workspace ready in {workspace.setup_seconds:.1f}s at {workspace.path}")
        stage(arm, ev.STAGE_BUILDING)
        build = _build_arm(
            arm,
            cfg=cfg,
            prompt=prompt,
            builder=runner_factory(cfg.builder),
            workspace=workspace,
            arm_dir=arm_dir,
            log=emit,
            events=emit_event,
        )
        emit(f"[{arm}] running {len(cfg.probes)} functional probes")
        stage(arm, ev.STAGE_PROBES)
        probe_results = run_probes(
            cfg.probes,
            workspace.path,
            arm_dir / "probe-scratch",
            on_result=lambda result, index, total: emit_event(
                ev.Event(
                    kind=ev.PROBE_RESULT,
                    arm=arm,
                    payload={
                        "name": result.name,
                        "passed": result.passed,
                        "index": index,
                        "total": total,
                    },
                )
            ),
        )
        emit(f"[{arm}] probe pass rate: {pass_rate(probe_results):.0%}")
        emit(f"[{arm}] collecting quantitative metrics")
        stage(arm, ev.STAGE_METRICS)
        metric_summary = collect(workspace.path, arm_dir / "metrics")
        emit_event(ev.Event(kind=ev.METRICS_READY, arm=arm, payload=dict(metric_summary)))
        stage(arm, ev.STAGE_GATE)
        native_gate = gate(workspace.path, arm_dir / "metrics") if cfg.run.run_native_gate else {
            "present": False
        }
        emit_event(ev.Event(kind=ev.GATE_RESULT, arm=arm, payload=dict(native_gate)))
        stage(arm, ev.STAGE_DONE)
        results: dict[str, object] = {
            "setup": {"seconds": round(workspace.setup_seconds, 1), "log": workspace.setup_log},
            "build": build,
            "probes": {
                "results": [result.as_dict() for result in probe_results],
                "pass_rate": round(pass_rate(probe_results), 3),
            },
            "metrics": metric_summary,
            "native_gate": native_gate,
        }
        _write_json(arm_dir / "arm_results.json", results)
        authored = changed_since_start(workspace.path)
        return _ArmOutcome(
            results=results,
            bundle=bundle_workspace(workspace.path, cfg.judge, authored),
        )

    if cfg.run.parallel_arms:
        with ThreadPoolExecutor(max_workers=len(ARMS)) as pool:
            futures = {arm: pool.submit(run_arm, arm) for arm in ARMS}
            outcomes = {arm: future.result() for arm, future in futures.items()}
    else:
        outcomes = {arm: run_arm(arm) for arm in ARMS}
    arms = {arm: outcome.results for arm, outcome in outcomes.items()}
    bundles = {arm: outcome.bundle for arm, outcome in outcomes.items()}

    emit(
        "judging bundles: "
        + ", ".join(f"{arm}: {bundle.file_count} files" for arm, bundle in bundles.items())
    )
    emit_event(
        ev.Event(
            kind=ev.JUDGING_STARTED,
            payload={
                "bundles": {arm: bundle.file_count for arm, bundle in bundles.items()},
                "expected_judgments": len(cfg.judge.panel) * 2,
            },
        )
    )
    judge_runners = {member.identity: runner_factory(member) for member in cfg.judge.panel}
    # A neutral, empty CWD outside any repository: judge CLIs ingest
    # instruction files from — and reveal the path of — their working
    # directory, so inheriting the harness CWD (this pack!) would unblind
    # every judge. The prefix is deliberately generic.
    panel_cwd = Path(tempfile.mkdtemp(prefix="code-review-"))
    judgments, judge_failures = run_panel(
        spec_text=cfg.spec_text,
        bundles=bundles,
        settings=cfg.judge,
        seed=cfg.run.seed,
        runners=judge_runners,
        working_directory=str(panel_cwd),
        on_judgment=lambda judgment: emit_event(
            ev.Event(
                kind=ev.JUDGMENT,
                payload={
                    "judge": judgment.judge,
                    "order_index": judgment.order_index,
                    "preference_arm": judgment.preference_arm,
                    "preference_strength": judgment.preference_strength,
                },
            )
        ),
        on_failure=lambda failure: emit_event(
            ev.Event(kind=ev.JUDGE_FAILED, payload=dict(failure))
        ),
    )
    shutil.rmtree(panel_cwd, ignore_errors=True)
    emit(f"collected {len(judgments)} judgments, {len(judge_failures)} judge failures")
    aggregate = aggregate_judgments(judgments, (ARMS[0], ARMS[1]))

    results: dict[str, object] = {
        "meta": manifest,
        "arms": arms,
        "judging": {
            "bundles": {
                arm: {
                    "file_count": bundle.file_count,
                    "total_chars": bundle.total_chars,
                    "truncated_files": list(bundle.truncated_files),
                }
                for arm, bundle in bundles.items()
            },
            "judgments": [judgment.as_dict() for judgment in judgments],
            "failures": judge_failures,
            "aggregate": aggregate,
        },
    }
    _write_json(run_dir / "results.json", results)
    (run_dir / "report.md").write_text(render_report(results), encoding="utf-8")

    if not cfg.run.keep_workspaces:
        shutil.rmtree(arms_dir, ignore_errors=True)
    emit(f"report: {run_dir / 'report.md'}")
    emit_event(
        ev.Event(
            kind=ev.RUN_FINISHED,
            payload={"report": str(run_dir / "report.md"), "aggregate": aggregate},
        )
    )
    return BenchmarkRun(run_dir=run_dir, results=results)
