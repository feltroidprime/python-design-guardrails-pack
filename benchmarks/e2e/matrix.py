"""Parallel, resumable benchmark campaigns over declared dimensions."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import threading
import tomllib
from typing import TYPE_CHECKING

from benchmarks.e2e.agents import AgentRunner, RunnerFactory
from benchmarks.e2e.config import (
    ARMS,
    PHASE_BUILD,
    PHASE_MAINTENANCE,
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
    template_identity: dict[str, object]
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
    _reject_unknown(
        section, {"provider", "model", "effort", "binary", "family"}, where=where
    )
    provider = _text(section, "provider", where=where)
    optional: dict[str, str | None] = {}
    for key in ("model", "effort", "binary", "family"):
        value = section.get(key)
        if value is not None and not isinstance(value, str):
            raise ConfigError(f"{where}: {key!r} must be a string when present")
        optional[key] = value.strip() or None if isinstance(value, str) else None
    role = RoleSettings(provider=provider, **optional)
    return replace(role, family=model_family(role))


def model_family(role: RoleSettings) -> str:
    """Normalize provider/model identities into bias-relevant model families."""
    if role.provider == "claude":
        if role.family not in (None, "claude"):
            raise ConfigError("claude roles cannot override their model family")
        return "claude"
    if role.provider == "codex":
        if role.family not in (None, "gpt"):
            raise ConfigError("codex roles cannot override their model family")
        return "gpt"
    if role.model is None:
        raise ConfigError(
            "opencode roles must declare a model so the family-disjointness rule "
            "can be enforced"
        )
    if role.family is None:
        raise ConfigError(
            "opencode roles must declare a canonical family so the "
            "family-disjointness rule can be enforced"
        )
    return role.family.casefold()


def _git_output(repo_root: Path, *arguments: str) -> str:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    completed = subprocess.run(
        ("git", "-C", str(repo_root), *arguments),
        capture_output=True,
        text=True,
        errors="replace",
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise ConfigError(
            f"could not resolve campaign template {arguments!r}: "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _template_source_paths(repo_root: Path) -> tuple[str, ...]:
    listed = _git_output(
        repo_root,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        "copier.yml",
        "template",
    )
    return tuple(sorted(item for item in listed.split("\0") if item))


def _template_source_digest(repo_root: Path, paths: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for relative in paths:
        source = repo_root / relative
        if source.is_symlink():
            raise ConfigError(
                f"campaign template contains unsupported symlink: {relative}"
            )
        if source.is_file():
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(source.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _resolve_template_identity(repo_root: Path, vcs_ref: str) -> dict[str, object]:
    """Resolve once so planning, execution, and resume share one identity."""
    revision = _git_output(repo_root, "rev-parse", f"{vcs_ref}^{{commit}}")
    version = vcs_ref
    source_digest: str | None = None
    dirty = False
    if vcs_ref == "HEAD":
        dirty = bool(
            _git_output(
                repo_root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                "copier.yml",
                "template",
            )
        )
        version = _git_output(repo_root, "describe", "--tags", "--always")
        if dirty:
            version += "-dirty"
        paths = _template_source_paths(repo_root)
        source_digest = _template_source_digest(repo_root, paths)
    return {
        "version": version,
        "vcs_ref": vcs_ref,
        "revision": revision,
        "source_digest": source_digest,
        "dirty": dirty,
    }


def _create_template_snapshot(
    repo_root: Path,
    snapshot_root: Path,
    *,
    identity: dict[str, object],
) -> str:
    """Commit the resolved template bytes into an immutable temporary repo."""
    dirty = identity.get("dirty") is True
    paths: tuple[str, ...] | None = None
    if dirty:
        paths = _template_source_paths(repo_root)
        try:
            for relative in paths:
                source = repo_root / relative
                if source.is_symlink():
                    raise ConfigError(
                        f"campaign template contains unsupported symlink: {relative}"
                    )
                if not source.is_file():
                    continue
                destination = snapshot_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination, follow_symlinks=False)
        except OSError as error:
            raise ConfigError(
                f"could not snapshot campaign template: {error}"
            ) from error
    else:
        revision = identity.get("revision")
        assert isinstance(revision, str)
        completed = subprocess.run(
            (
                "git",
                "-C",
                str(repo_root),
                "archive",
                "--format=tar",
                revision,
                "copier.yml",
                "template",
            ),
            capture_output=True,
            env={
                key: value
                for key, value in os.environ.items()
                if not key.startswith("GIT_")
            },
            check=False,
        )
        if completed.returncode != 0:
            raise ConfigError(
                "could not archive pinned campaign template: "
                + completed.stderr.decode(errors="replace").strip()
            )
        with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
            symlinks = [
                member.name
                for member in archive.getmembers()
                if member.issym() or member.islnk()
            ]
            if symlinks:
                raise ConfigError(
                    "campaign template archive contains unsupported symlinks: "
                    + ", ".join(symlinks)
                )
            archive.extractall(snapshot_root, filter="data")
    expected_digest = identity.get("source_digest")
    if paths is not None and isinstance(expected_digest, str):
        actual_digest = _template_source_digest(snapshot_root, paths)
        if actual_digest != expected_digest:
            raise ConfigError(
                "campaign template identity changed while creating its pinned snapshot; "
                "re-run the matrix"
            )
    _git_output(snapshot_root, "init", "--quiet", "--initial-branch=main")
    _git_output(snapshot_root, "add", "--all")
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
        }
    )
    committed = subprocess.run(
        (
            "git",
            "-C",
            str(snapshot_root),
            "-c",
            "user.name=guardrails-benchmark",
            "-c",
            "user.email=guardrails-benchmark@localhost",
            "commit",
            "--quiet",
            "--message=pinned campaign template",
        ),
        capture_output=True,
        text=True,
        errors="replace",
        env=environment,
        check=False,
    )
    if committed.returncode != 0:
        raise ConfigError(
            f"could not commit pinned campaign template: {committed.stderr.strip()}"
        )
    return _git_output(snapshot_root, "rev-parse", "HEAD")


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
    if len(set(seeds)) != len(seeds):
        raise ConfigError(f"{where}: [matrix]: seeds must be unique")
    variants = _strings(
        raw_matrix.get("variants"), key="variants", where=f"{where}: [matrix]"
    )
    if len(set(variants)) != len(variants):
        raise ConfigError(f"{where}: [matrix]: variants must be unique")
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
    template_identity = _resolve_template_identity(repo_root, vcs_ref)

    raw_builders = raw.get("builders")
    if not isinstance(raw_builders, list) or not raw_builders:
        raise ConfigError(f"{where}: [[builders]] must be a non-empty array of tables")
    builders = tuple(
        _role(item, where=f"{where}: builders[{index}]")
        for index, item in enumerate(raw_builders)
    )
    if len(set(builders)) != len(builders):
        raise ConfigError(f"{where}: [[builders]] entries must be unique")

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
        template_identity=template_identity,
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
    maintenance = (
        None
        if cfg.maintenance is None
        else {
            "spec_text": cfg.maintenance.spec_text,
            "probes": [asdict(probe) for probe in cfg.maintenance.probes],
        }
    )
    evidence = {
        "project": asdict(cfg.project),
        "build": {
            "charter_text": cfg.charter_text,
            "spec_text": cfg.spec_text,
            "probes": [asdict(probe) for probe in cfg.probes],
        },
        "maintenance": maintenance,
        "builder": asdict(cfg.builder),
        "judge": asdict(cfg.judge),
        "tools": asdict(cfg.tools),
        "run": {
            "run_native_gate": cfg.run.run_native_gate,
            "parallel_arms": cfg.run.parallel_arms,
            "install_timeout_seconds": cfg.run.install_timeout_seconds,
            "tests_timeout_seconds": cfg.run.tests_timeout_seconds,
            "gate_timeout_seconds": cfg.run.gate_timeout_seconds,
        },
        "template": {
            "variant": cfg.template.variant,
            "answers": cfg.template.answers,
        },
    }
    evidence_json = json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), default=str
    )
    builder = asdict(cfg.builder)
    builder["family"] = model_family(cfg.builder)
    identity: dict[str, object] = {
        "campaign": matrix.run.label,
        "app": cfg.project.name,
        "builder": builder,
        "seed": cfg.run.seed,
        "variant": cfg.template.variant,
        "repetition": repetition,
        "template_vcs_ref": cfg.template.vcs_ref,
        "template_identity": dict(matrix.template_identity),
        "template_answers": dict(cfg.template.answers),
        "judges": [
            {
                **asdict(member),
                "identity": member.identity,
                "family": model_family(member),
            }
            for member in cfg.judge.panel
        ],
        "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode()).hexdigest(),
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
                            inherit_unspecified=False,
                        )
                        cfg = replace(
                            cfg,
                            builder=replace(
                                cfg.builder,
                                binary=builder.binary,
                                family=builder.family,
                            ),
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
                                answers={
                                    **named_answers,
                                    **app.template.explicit_answers,
                                },
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


def _completed_cell_ids(path: Path, cells: tuple[MatrixCell, ...]) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    evidence_by_cell: defaultdict[str, set[tuple[str, str]]] = defaultdict(set)
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
        phase = row.get("phase", PHASE_BUILD) if isinstance(row, dict) else None
        cell_id = matrix.get("cell_id") if isinstance(matrix, dict) else None
        if isinstance(cell_id, str) and isinstance(arm, str) and isinstance(phase, str):
            evidence_by_cell[cell_id].add((arm, phase))
    required_by_cell = {
        cell.cell_id: {
            (arm, phase)
            for arm in ARMS
            for phase in (
                (PHASE_BUILD, PHASE_MAINTENANCE)
                if cell.config.maintenance is not None
                else (PHASE_BUILD,)
            )
        }
        for cell in cells
    }
    return frozenset(
        cell_id
        for cell_id, required in required_by_cell.items()
        if required <= evidence_by_cell[cell_id]
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

    complete_ids = _completed_cell_ids(
        matrix.run.output_root / REGISTRY_FILENAME, cells
    )
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

    runs_by_id: dict[str, BenchmarkRun] = {}
    with ExitStack() as stack:
        current_identity = _resolve_template_identity(
            repo_root, matrix.template_vcs_ref
        )
        if current_identity != matrix.template_identity:
            raise ConfigError(
                "campaign template identity changed after planning; "
                "re-run the matrix so every cell uses one pinned identity"
            )
        snapshot = Path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix="guardrails-matrix-template-")
            )
        )
        template_source_root = snapshot
        template_vcs_ref = _create_template_snapshot(
            repo_root, snapshot, identity=matrix.template_identity
        )

        def execute(cell: MatrixCell) -> BenchmarkRun:
            from benchmarks.e2e.orchestrator import run_benchmark

            return run_benchmark(
                cell.config,
                repo_root=repo_root,
                runner_factory=capped_factory,
                metrics_collector=metrics_collector,
                gate_runner=gate_runner,
                log=log,
                template_source_root=template_source_root,
                template_vcs_ref=template_vcs_ref,
                template_identity=dict(matrix.template_identity),
            )

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
