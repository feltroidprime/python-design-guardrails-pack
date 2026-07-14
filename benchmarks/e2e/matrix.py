"""Parallel, resumable benchmark campaigns over declared dimensions."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import threading
import tomllib
from typing import TYPE_CHECKING

from benchmarks.e2e.agents import AgentRunner, RunnerFactory
from benchmarks.e2e.config import (
    ARMS,
    PROVIDERS,
    BenchmarkConfig,
    ConfigError,
    JudgeSettings,
    RoleSettings,
    apply_builder_overrides,
    load_config,
    template_variant_answers,
)
from benchmarks.e2e.registry import REGISTRY_FILENAME

if TYPE_CHECKING:
    from benchmarks.e2e.orchestrator import (
        BenchmarkRun,
        GateRunner,
        Logger,
        MetricsCollector,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixRunSettings:
    output_root: Path
    label: str
    headless_llm_path: Path


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixConfig:
    source_path: Path
    run: MatrixRunSettings
    apps: tuple[BenchmarkConfig, ...]
    builders: tuple[RoleSettings, ...]
    seeds: tuple[int, ...]
    variants: tuple[str, ...]
    variant_answers: dict[str, dict[str, object]]
    repetitions: int
    template_vcs_ref: str
    judge_panel: tuple[RoleSettings, ...]
    concurrency_caps: dict[str, int]


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixCell:
    config: BenchmarkConfig
    dimensions: dict[str, object]

    @property
    def cell_id(self) -> str:
        return str(self.dimensions["cell_id"])

    @property
    def description(self) -> str:
        builder = self.dimensions["builder"]
        assert isinstance(builder, dict)
        return (
            f"{self.cell_id} app={self.dimensions['app']} "
            f"builder={builder['provider']}:{builder.get('model') or 'default'} "
            f"seed={self.dimensions['seed']} variant={self.dimensions['variant']} "
            f"repetition={self.dimensions['repetition']}"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixResult:
    planned: tuple[MatrixCell, ...]
    completed: tuple[MatrixCell, ...]
    skipped: tuple[MatrixCell, ...]
    runs: tuple[BenchmarkRun, ...]


def _table(raw: dict[str, object], key: str, *, where: str) -> dict[str, object]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: missing required table [{key}]")
    return value


def _reject_unknown(
    section: dict[str, object], allowed: set[str], *, where: str
) -> None:
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ConfigError(
            f"{where}: unknown keys {unknown}; allowed: {sorted(allowed)}"
        )


def _text(section: dict[str, object], key: str, *, where: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: {key!r} must be a non-empty string")
    return value.strip()


def _role(section: object, *, where: str) -> RoleSettings:
    if not isinstance(section, dict):
        raise ConfigError(f"{where}: must be a table")
    _reject_unknown(section, {"provider", "model", "effort", "binary"}, where=where)
    provider = _text(section, "provider", where=where)
    optional: dict[str, str | None] = {}
    for key in ("model", "effort", "binary"):
        value = section.get(key)
        if value is not None and not isinstance(value, str):
            raise ConfigError(f"{where}: {key!r} must be a string when present")
        optional[key] = value.strip() or None if isinstance(value, str) else None
    return RoleSettings(provider=provider, **optional)


def model_family(role: RoleSettings) -> str:
    """Normalize provider/model identities into bias-relevant model families."""
    if role.provider == "claude":
        return "claude"
    if role.provider == "codex":
        return "gpt"
    model = (role.model or "opencode-default").lower()
    if "claude" in model or "anthropic" in model:
        return "claude"
    if "gpt" in model or "openai" in model or "codex" in model:
        return "gpt"
    return model.split("/", 1)[0]


def _paths(values: object, *, where: str, base: Path) -> tuple[Path, ...]:
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(item, str) for item in values)
    ):
        raise ConfigError(f"{where}: 'apps' must be a non-empty array of paths")
    return tuple(
        (base / item).resolve() if not Path(item).is_absolute() else Path(item)
        for item in values
    )


def _strings(values: object, *, key: str, where: str) -> tuple[str, ...]:
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(item, str) and item for item in values)
    ):
        raise ConfigError(f"{where}: {key!r} must be a non-empty array of strings")
    return tuple(values)


def _seeds(values: object, *, where: str) -> tuple[int, ...]:
    if (
        not isinstance(values, list)
        or not values
        or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in values
        )
    ):
        raise ConfigError(f"{where}: 'seeds' must be a non-empty array of integers")
    return tuple(values)


def load_matrix_config(path: Path, *, repo_root: Path) -> MatrixConfig:
    """Read and fully validate a campaign before any output is created."""
    if not path.is_file():
        raise ConfigError(f"matrix config file not found: {path}")
    try:
        raw: dict[str, object] = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: invalid TOML: {error}") from error
    where = str(path)
    _reject_unknown(
        raw,
        {"run", "matrix", "template", "builders", "judge", "concurrency"},
        where=where,
    )

    raw_run = _table(raw, "run", where=where)
    _reject_unknown(
        raw_run, {"output_root", "label", "headless_llm_path"}, where=f"{where}: [run]"
    )
    output_root = Path(
        _text(raw_run, "output_root", where=f"{where}: [run]")
    ).expanduser()
    if not output_root.is_absolute():
        output_root = (repo_root / output_root).resolve()
    if output_root.resolve().is_relative_to(repo_root.resolve()):
        raise ConfigError(
            f"{where}: [run]: output_root must stay outside the pack working tree"
        )
    headless = Path(
        _text(raw_run, "headless_llm_path", where=f"{where}: [run]")
    ).expanduser()
    if not headless.is_absolute():
        headless = (repo_root / headless).resolve()
    run = MatrixRunSettings(
        output_root=output_root,
        label=_text(raw_run, "label", where=f"{where}: [run]"),
        headless_llm_path=headless,
    )

    raw_matrix = _table(raw, "matrix", where=where)
    _reject_unknown(
        raw_matrix,
        {"apps", "seeds", "variants", "repetitions"},
        where=f"{where}: [matrix]",
    )
    app_paths = _paths(
        raw_matrix.get("apps"), where=f"{where}: [matrix]", base=path.parent
    )
    apps = tuple(load_config(app_path, repo_root=repo_root) for app_path in app_paths)
    if len({app.project.name for app in apps}) != len(apps):
        raise ConfigError(f"{where}: [matrix]: app project names must be unique")
    seeds = _seeds(raw_matrix.get("seeds"), where=f"{where}: [matrix]")
    variants = _strings(
        raw_matrix.get("variants"), key="variants", where=f"{where}: [matrix]"
    )
    variant_answers = {
        variant: template_variant_answers(
            variant, where=f"{where}: [matrix]", repo_root=repo_root
        )
        for variant in variants
    }
    repetitions = raw_matrix.get("repetitions", 1)
    if (
        isinstance(repetitions, bool)
        or not isinstance(repetitions, int)
        or repetitions <= 0
    ):
        raise ConfigError(
            f"{where}: [matrix]: 'repetitions' must be a positive integer"
        )

    raw_template = _table(raw, "template", where=where)
    _reject_unknown(raw_template, {"vcs_ref"}, where=f"{where}: [template]")
    vcs_ref = _text(raw_template, "vcs_ref", where=f"{where}: [template]")

    raw_builders = raw.get("builders")
    if not isinstance(raw_builders, list) or not raw_builders:
        raise ConfigError(f"{where}: [[builders]] must be a non-empty array of tables")
    builders = tuple(
        _role(item, where=f"{where}: builders[{index}]")
        for index, item in enumerate(raw_builders)
    )

    raw_judge = _table(raw, "judge", where=where)
    _reject_unknown(raw_judge, {"panel"}, where=f"{where}: [judge]")
    raw_panel = raw_judge.get("panel")
    if not isinstance(raw_panel, list) or not raw_panel:
        raise ConfigError(f"{where}: [[judge.panel]] must contain at least one member")
    panel = tuple(
        _role(item, where=f"{where}: judge.panel[{index}]")
        for index, item in enumerate(raw_panel)
    )

    builder_families = {model_family(builder): builder for builder in builders}
    for judge in panel:
        family = model_family(judge)
        if family in builder_families:
            builder = builder_families[family]
            raise ConfigError(
                "judge/builder model-family family-disjointness rule violated: "
                f"family {family!r} is used by builder {builder.identity} and judge {judge.identity}"
            )

    raw_caps = _table(raw, "concurrency", where=where)
    _reject_unknown(raw_caps, set(PROVIDERS), where=f"{where}: [concurrency]")
    caps: dict[str, int] = {}
    for provider in PROVIDERS:
        value = raw_caps.get(provider, 1)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConfigError(
                f"{where}: [concurrency]: {provider!r} must be a positive integer"
            )
        caps[provider] = value

    return MatrixConfig(
        source_path=path.resolve(),
        run=run,
        apps=apps,
        builders=builders,
        seeds=seeds,
        variants=variants,
        variant_answers=variant_answers,
        repetitions=repetitions,
        template_vcs_ref=vcs_ref,
        judge_panel=panel,
        concurrency_caps=caps,
    )


def _cell_dimensions(
    matrix: MatrixConfig,
    cfg: BenchmarkConfig,
    *,
    repetition: int,
) -> dict[str, object]:
    prompt = f"{cfg.charter_text.strip()}\n\n{cfg.spec_text.strip()}\n".encode()
    identity: dict[str, object] = {
        "campaign": matrix.run.label,
        "app": cfg.project.name,
        "builder": {
            "provider": cfg.builder.provider,
            "model": cfg.builder.model,
            "effort": cfg.builder.effort,
        },
        "seed": cfg.run.seed,
        "variant": cfg.template.variant,
        "repetition": repetition,
        "template_vcs_ref": cfg.template.vcs_ref,
        "template_answers": dict(cfg.template.answers),
        "judges": [member.identity for member in cfg.judge.panel],
        "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    identity["cell_id"] = hashlib.sha256(canonical.encode()).hexdigest()[:20]
    return identity


def plan_matrix(matrix: MatrixConfig) -> tuple[MatrixCell, ...]:
    """Expand dimensions deterministically without creating any output."""
    cells: list[MatrixCell] = []
    for repetition in range(1, matrix.repetitions + 1):
        for app in matrix.apps:
            for seed in matrix.seeds:
                for variant in matrix.variants:
                    named_answers = matrix.variant_answers[variant]
                    for builder in matrix.builders:
                        cfg = apply_builder_overrides(
                            app,
                            provider=builder.provider,
                            model=builder.model,
                            effort=builder.effort,
                        )
                        cfg = replace(
                            cfg,
                            run=replace(
                                cfg.run,
                                output_root=matrix.run.output_root,
                                seed=seed,
                                headless_llm_path=matrix.run.headless_llm_path,
                            ),
                            template=replace(
                                cfg.template,
                                vcs_ref=matrix.template_vcs_ref,
                                variant=variant,
                                answers={**named_answers, **app.template.answers},
                            ),
                            judge=JudgeSettings(
                                panel=matrix.judge_panel,
                                timeout_seconds=app.judge.timeout_seconds,
                                max_bundle_chars=app.judge.max_bundle_chars,
                                max_file_chars=app.judge.max_file_chars,
                                exclude=app.judge.exclude,
                                redact=app.judge.redact,
                            ),
                        )
                        dimensions = _cell_dimensions(
                            matrix, cfg, repetition=repetition
                        )
                        cfg = replace(
                            cfg,
                            run=replace(
                                cfg.run,
                                label=f"{matrix.run.label}-{dimensions['cell_id']}",
                            ),
                            matrix_dimensions=dimensions,
                        )
                        cells.append(MatrixCell(config=cfg, dimensions=dimensions))
    return tuple(cells)


def _completed_cell_ids(path: Path) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    arms_by_cell: defaultdict[str, set[str]] = defaultdict(set)
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ConfigError(
                f"{path}:{line_number}: invalid registry JSON: {error.msg}"
            ) from error
        matrix = row.get("matrix") if isinstance(row, dict) else None
        arm = row.get("arm") if isinstance(row, dict) else None
        cell_id = matrix.get("cell_id") if isinstance(matrix, dict) else None
        if isinstance(cell_id, str) and isinstance(arm, str):
            arms_by_cell[cell_id].add(arm)
    required = set(ARMS)
    return frozenset(
        cell_id for cell_id, arms in arms_by_cell.items() if required <= arms
    )


class _CappedRunner:
    def __init__(self, runner: AgentRunner, semaphore: threading.Semaphore) -> None:
        self._runner = runner
        self._semaphore = semaphore

    def run(self, prompt: str, **kwargs: object):  # noqa: ANN201
        with self._semaphore:
            return self._runner.run(prompt, **kwargs)


def run_matrix(
    matrix: MatrixConfig,
    *,
    repo_root: Path,
    runner_factory: RunnerFactory,
    metrics_collector: MetricsCollector | None = None,
    gate_runner: GateRunner | None = None,
    dry_run: bool = False,
    log: Logger = print,
) -> MatrixResult:
    """Plan or execute a campaign, skipping registry-complete cells."""
    cells = plan_matrix(matrix)
    log(f"planned matrix cells: {len(cells)}")
    for index, cell in enumerate(cells, start=1):
        log(f"[{index}/{len(cells)}] {cell.description}")
    if dry_run:
        return MatrixResult(planned=cells, completed=(), skipped=(), runs=())

    complete_ids = _completed_cell_ids(matrix.run.output_root / REGISTRY_FILENAME)
    skipped = tuple(cell for cell in cells if cell.cell_id in complete_ids)
    pending = tuple(cell for cell in cells if cell.cell_id not in complete_ids)
    if skipped:
        log(f"resume: skipping {len(skipped)} completed cells")

    semaphores = {
        provider: threading.BoundedSemaphore(cap)
        for provider, cap in matrix.concurrency_caps.items()
    }

    def capped_factory(role: RoleSettings) -> AgentRunner:
        return _CappedRunner(runner_factory(role), semaphores[role.provider])

    def execute(cell: MatrixCell) -> BenchmarkRun:
        from benchmarks.e2e.orchestrator import run_benchmark

        return run_benchmark(
            cell.config,
            repo_root=repo_root,
            runner_factory=capped_factory,
            metrics_collector=metrics_collector,
            gate_runner=gate_runner,
            log=log,
        )

    runs_by_id: dict[str, BenchmarkRun] = {}
    with ExitStack() as stack:
        executors = {
            provider: stack.enter_context(
                ThreadPoolExecutor(max_workers=matrix.concurrency_caps[provider])
            )
            for provider in {cell.config.builder.provider for cell in pending}
        }
        futures: dict[Future[BenchmarkRun], MatrixCell] = {
            executors[cell.config.builder.provider].submit(execute, cell): cell
            for cell in pending
        }
        for future in as_completed(futures):
            cell = futures[future]
            runs_by_id[cell.cell_id] = future.result()
            log(f"completed matrix cell: {cell.cell_id}")

    completed = tuple(cell for cell in pending if cell.cell_id in runs_by_id)
    runs = tuple(runs_by_id[cell.cell_id] for cell in completed)
    return MatrixResult(planned=cells, completed=completed, skipped=skipped, runs=runs)
