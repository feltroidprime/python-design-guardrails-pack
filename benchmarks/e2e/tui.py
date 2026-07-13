"""Live terminal dashboard for watching a benchmark run.

Two arms side by side, judges revealing verdicts one by one — designed to be
recorded. Rendering is driven by the orchestrator's structured events plus a
cheap filesystem poll of both workspaces (file/LOC counters tick while the
builders are writing code). This module is the only one importing rich; it is
imported lazily by the launcher so the deterministic test suite never needs
the dependency.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
import time

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from benchmarks.e2e import events as ev
from benchmarks.e2e.agents import RunnerFactory
from benchmarks.e2e.config import ARM_BARE, ARM_GUARDRAILS, ARMS, BenchmarkConfig
from benchmarks.e2e.metrics import python_files
from benchmarks.e2e.orchestrator import BenchmarkRun, run_benchmark

_ARM_TITLES = {ARM_BARE: "BARE REPO", ARM_GUARDRAILS: "TEMPLATE REPO"}
_ARM_COLORS = {ARM_BARE: "cyan", ARM_GUARDRAILS: "magenta"}
_STAGE_STYLES = {
    ev.STAGE_WORKSPACE: ("PREPARING", "grey62"),
    ev.STAGE_BUILDING: ("AGENT BUILDING", "yellow"),
    ev.STAGE_PROBES: ("FUNCTIONAL PROBES", "blue"),
    ev.STAGE_METRICS: ("MEASURING", "cyan"),
    ev.STAGE_GATE: ("NATIVE GATE", "magenta"),
    ev.STAGE_DONE: ("DONE", "green"),
}


def _mmss(seconds: float) -> str:
    minutes, secs = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{secs:02d}"


@dataclass(slots=True)
class _ArmView:
    stage: str = ""
    stage_started: float = 0.0
    build: dict[str, object] | None = None
    probes: list[tuple[str, bool]] = field(default_factory=list)
    probe_total: int = 0
    metrics: dict[str, object] | None = None
    gate: dict[str, object] | None = None
    files: int = 0
    loc: int = 0
    last_file: str = ""


class _Dashboard:
    """Thread-safe reducer from orchestrator events to a rich renderable."""

    def __init__(self, cfg: BenchmarkConfig) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._arms: dict[str, _ArmView] = {arm: _ArmView() for arm in ARMS}
        self._workspaces: dict[str, Path] = {}
        self._judges: list[str] = [member.identity for member in cfg.judge.panel]
        self._verdicts: dict[tuple[str, int], tuple[str, str]] = {}
        self._judging = False
        self._aggregate: dict[str, object] = {}
        self._run_id = ""
        self._report = ""
        self._log_lines: list[str] = []
        self._started = time.monotonic()
        self._spinner = Spinner("dots", style="yellow")

    def log_line(self, message: str) -> None:
        with self._lock:
            self._log_lines = ([*self._log_lines, message])[-3:]

    def apply_event(self, event: ev.Event) -> None:
        with self._lock:
            self._apply(event)

    def _apply(self, event: ev.Event) -> None:
        payload = event.payload
        if event.kind == ev.RUN_STARTED:
            self._run_id = str(payload.get("run_id", ""))
            run_dir = Path(str(payload.get("run_dir", "")))
            for arm in ARMS:
                self._workspaces[arm] = run_dir / "arms" / arm / "workspace"
                self._arms[arm].probe_total = len(self._cfg.probes)
        elif event.kind == ev.ARM_STAGE and event.arm in self._arms:
            view = self._arms[event.arm]
            view.stage = str(payload.get("stage", ""))
            view.stage_started = time.monotonic()
        elif event.kind == ev.BUILD_FINISHED and event.arm in self._arms:
            self._arms[event.arm].build = dict(payload)
        elif event.kind == ev.PROBE_RESULT and event.arm in self._arms:
            view = self._arms[event.arm]
            view.probes.append((str(payload.get("name", "")), bool(payload.get("passed"))))
            view.probe_total = int(payload.get("total", view.probe_total) or view.probe_total)
        elif event.kind == ev.METRICS_READY and event.arm in self._arms:
            self._arms[event.arm].metrics = dict(payload)
        elif event.kind == ev.GATE_RESULT and event.arm in self._arms:
            self._arms[event.arm].gate = dict(payload)
        elif event.kind == ev.JUDGING_STARTED:
            self._judging = True
        elif event.kind == ev.JUDGMENT:
            key = (str(payload.get("judge", "")), int(payload.get("order_index", 0) or 0))
            self._verdicts[key] = (
                str(payload.get("preference_arm", "")),
                str(payload.get("preference_strength", "")),
            )
        elif event.kind == ev.JUDGE_FAILED:
            key = (str(payload.get("judge", "")), int(payload.get("order_index", 0) or 0))
            self._verdicts[key] = ("failed", "")
        elif event.kind == ev.RUN_FINISHED:
            self._report = str(payload.get("report", ""))
            aggregate = payload.get("aggregate")
            if isinstance(aggregate, dict):
                self._aggregate = aggregate

    def poll_workspaces(self) -> None:
        """Cheap filesystem pulse so the panels tick while agents write code."""
        snapshots: dict[str, tuple[int, int, str]] = {}
        for arm, workspace in list(self._workspaces.items()):
            if not workspace.is_dir():
                continue
            try:
                sources, tests = python_files(workspace)
                paths = [*sources, *tests]
                loc = 0
                latest: tuple[float, str] = (0.0, "")
                for path in paths:
                    try:
                        text = path.read_text(encoding="utf-8", errors="replace")
                        stamp = path.stat().st_mtime
                    except OSError:
                        continue
                    loc += sum(1 for line in text.splitlines() if line.strip())
                    if stamp > latest[0]:
                        latest = (stamp, path.relative_to(workspace).as_posix())
                snapshots[arm] = (len(paths), loc, latest[1])
            except OSError:
                continue
        with self._lock:
            for arm, (files, loc, last_file) in snapshots.items():
                view = self._arms[arm]
                view.files, view.loc = files, loc
                if last_file:
                    view.last_file = last_file

    def _stage_line(self, view: _ArmView) -> RenderableType:
        title, style = _STAGE_STYLES.get(view.stage, ("STARTING", "grey62"))
        elapsed = _mmss(time.monotonic() - view.stage_started) if view.stage_started else ""
        line = Table.grid(padding=(0, 1))
        line.add_column()
        line.add_column()
        line.add_column()
        marker: RenderableType
        if view.stage == ev.STAGE_DONE:
            marker = Text("●", style="bold green")
        else:
            marker = self._spinner
        line.add_row(marker, Text(title, style=f"bold {style}"), Text(elapsed, style="dim"))
        return line

    def _probe_strip(self, view: _ArmView) -> Text:
        strip = Text("probes  ", style="bold")
        for _name, passed in view.probes:
            strip.append("✔" if passed else "✘", style="green" if passed else "bold red")
        remaining = max(0, view.probe_total - len(view.probes))
        strip.append("·" * remaining, style="grey42")
        if view.probes:
            passed_count = sum(1 for _name, ok in view.probes if ok)
            strip.append(f"  {passed_count}/{view.probe_total}", style="bold")
        return strip

    def _metric_line(self, view: _ArmView) -> Text:
        text = Text()
        if view.metrics is None:
            return text
        own = view.metrics.get("own_tests")
        coverage = view.metrics.get("coverage")
        ruff = view.metrics.get("ruff")
        pyright = view.metrics.get("basedpyright")
        radon = view.metrics.get("radon")
        parts: list[str] = []
        if isinstance(own, dict):
            counts = own.get("counts")
            passed = counts.get("passed", 0) if isinstance(counts, dict) else 0
            mark = "✔" if own.get("exit_code") == 0 else "✘"
            parts.append(f"tests {mark} {passed}")
        if isinstance(coverage, dict) and coverage.get("percent") is not None:
            parts.append(f"cov {coverage.get('percent')}%")
        if isinstance(ruff, dict) and ruff.get("violations") is not None:
            parts.append(f"ruff {ruff.get('violations')}")
        if isinstance(pyright, dict) and pyright.get("errors") is not None:
            parts.append(f"pyright {pyright.get('errors')}")
        if isinstance(radon, dict) and radon.get("average_complexity") is not None:
            parts.append(f"cc {radon.get('average_complexity')}")
        text.append(" · ".join(parts), style="bright_white")
        return text

    def _arm_panel(self, arm: str) -> Panel:
        view = self._arms[arm]
        color = _ARM_COLORS[arm]
        body: list[RenderableType] = [self._stage_line(view)]
        workspace = self._workspaces.get(arm)
        if workspace is not None:
            home = str(Path.home())
            display = str(workspace)
            if display.startswith(home):
                display = "~" + display[len(home):]
            body.append(
                Text(
                    f"📁 {display}",
                    style=f"dim link file://{workspace}",
                    overflow="fold",
                )
            )
        counters = Text()
        counters.append(f"{view.files}", style=f"bold {color}")
        counters.append(" py files · ", style="dim")
        counters.append(f"{view.loc}", style=f"bold {color}")
        counters.append(" loc", style="dim")
        body.append(counters)
        if view.last_file:
            body.append(Text(f"✎ {view.last_file}"[:58], style="italic dim"))
        if view.build is not None:
            build = view.build
            line = Text()
            if build.get("error"):
                line.append(f"build failed: {build.get('error')}"[:58], style="bold red")
            else:
                line.append("built in ", style="dim")
                line.append(f"{_mmss(float(build.get('duration_seconds') or 0))}", style="bold")
                line.append(f" · {build.get('tool_calls')} tools", style="dim")
                cost = build.get("cost_usd")
                if isinstance(cost, (int, float)):
                    line.append(f" · ${cost:.2f}", style="bold green")
            body.append(line)
        body.append(self._probe_strip(view))
        body.append(self._metric_line(view))
        if view.gate is not None and view.gate.get("present"):
            passed = bool(view.gate.get("passed"))
            body.append(
                Text(
                    f"native quality gate {'✔ green' if passed else '✘ red'}",
                    style="bold green" if passed else "bold red",
                )
            )
        return Panel(
            Group(*body),
            title=f"[bold {color}]{_ARM_TITLES[arm]}[/]",
            border_style=color,
            padding=(0, 1),
        )

    def _judge_panel(self) -> Panel:
        table = Table.grid(padding=(0, 2))
        table.add_column(min_width=28)
        table.add_column(min_width=20)
        table.add_column(min_width=20)
        for judge in self._judges:
            cells: list[RenderableType] = [Text(judge, style="bold")]
            for order in (0, 1):
                verdict = self._verdicts.get((judge, order))
                if verdict is None:
                    cells.append(
                        self._spinner if self._judging else Text("waiting", style="grey42")
                    )
                elif verdict[0] == "failed":
                    cells.append(Text("failed", style="bold red"))
                elif verdict[0] == "tie":
                    cells.append(Text("TIE", style="bold yellow"))
                else:
                    arm = verdict[0]
                    cells.append(
                        Text(
                            f"{_ARM_TITLES.get(arm, arm)} ({verdict[1]})",
                            style=f"bold {_ARM_COLORS.get(arm, 'white')}",
                        )
                    )
            table.add_row(*cells)
        subtitle = "blind A/B · both presentation orders · cross-family panel"
        return Panel(
            table,
            title="[bold]JUDGE PANEL[/]",
            subtitle=f"[dim]{subtitle}[/]",
            border_style="bright_black",
            padding=(0, 1),
        )

    def _header(self) -> Panel:
        elapsed = _mmss(time.monotonic() - self._started)
        line = Text()
        line.append("⚔ TEMPLATE VALUE BENCHMARK", style="bold bright_white")
        line.append("  ·  same agent, same spec, with vs without guardrails\n", style="dim")
        line.append(f"builder {self._cfg.builder.identity}", style="yellow")
        line.append(f"  ·  run {self._run_id or '…'}", style="dim")
        line.append(f"  ·  ⏱ {elapsed}", style="bold")
        return Panel(line, border_style="bright_black", padding=(0, 2))

    def _footer(self) -> RenderableType:
        if self._aggregate:
            preferences = self._aggregate.get("preferences")
            tally = Text("VERDICT  ", style="bold bright_white")
            if isinstance(preferences, dict):
                for arm, count in preferences.items():
                    label = _ARM_TITLES.get(str(arm), str(arm))
                    style = f"bold {_ARM_COLORS.get(str(arm), 'yellow')}"
                    tally.append(f"{label} {count}   ", style=style)
            if self._report:
                tally.append(f"\n{self._report}", style="dim")
            return Panel(tally, border_style="green", padding=(0, 2))
        ticker = Text("\n".join(self._log_lines[-3:]), style="dim", no_wrap=True)
        return Panel(ticker, border_style="bright_black", padding=(0, 2), height=5)

    def render(self) -> RenderableType:
        with self._lock:
            grid = Table.grid(expand=True)
            grid.add_column()
            grid.add_row(self._header())
            arm_row = Table.grid(expand=True)
            arm_row.add_column(ratio=1)
            arm_row.add_column(ratio=1)
            arm_row.add_row(self._arm_panel(ARM_BARE), self._arm_panel(ARM_GUARDRAILS))
            grid.add_row(arm_row)
            grid.add_row(self._judge_panel())
            grid.add_row(self._footer())
            return grid


def run_with_tui(
    cfg: BenchmarkConfig, *, repo_root: Path, runner_factory: RunnerFactory
) -> BenchmarkRun:
    """Run the benchmark while rendering the live dashboard on this terminal."""
    dashboard = _Dashboard(cfg)
    console = Console()
    outcome: list[BenchmarkRun] = []
    failure: list[BaseException] = []

    def worker() -> None:
        try:
            outcome.append(
                run_benchmark(
                    cfg,
                    repo_root=repo_root,
                    runner_factory=runner_factory,
                    log=dashboard.log_line,
                    events=dashboard.apply_event,
                )
            )
        except BaseException as error:  # noqa: BLE001 - re-raised on the main thread
            failure.append(error)

    thread = threading.Thread(target=worker, name="benchmark", daemon=True)
    started = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    console.print(f"[dim]benchmark started {started} — recording-friendly dashboard[/]")
    thread.start()
    with Live(dashboard.render(), console=console, refresh_per_second=6) as live:
        while thread.is_alive():
            dashboard.poll_workspaces()
            live.update(dashboard.render())
            time.sleep(0.25)
        thread.join()
        dashboard.poll_workspaces()
        live.update(dashboard.render())
    if failure:
        raise failure[0]
    return outcome[0]
