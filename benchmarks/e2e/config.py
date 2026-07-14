"""Typed configuration for the end-to-end value benchmark.

Every knob that can change the outcome — prompt, models, probes, analyzer
pins, judge panel — lives in one TOML file, so a run is reproducible from the
config alone. Unknown keys are rejected: a typo must fail loudly, not silently
fall back to a default that skews the comparison.
"""

from dataclasses import dataclass, field, replace
import fnmatch
from pathlib import Path
import re
import tomllib

ARM_BARE = "bare"
ARM_GUARDRAILS = "guardrails"
ARMS = (ARM_BARE, ARM_GUARDRAILS)
PHASE_BUILD = "build"
PHASE_MAINTENANCE = "maintenance"


def matches_exclude(relative_posix: str, patterns: tuple[str, ...]) -> bool:
    """Shared exclusion matcher for the symmetric application-deliverable scope.

    Used by the judge bundling and by coverage aggregation so both draw the
    same line between application code and repository infrastructure.
    """
    return any(
        fnmatch.fnmatch(relative_posix, pattern) or relative_posix == pattern.rstrip("/")
        for pattern in patterns
    )

PROVIDERS = ("claude", "codex", "opencode")

# Sanity floor: below this the app spec cannot describe a real application.
_MIN_SPEC_CHARS = 200
_VARIANT_ANSWERS = Path("benchmarks/config/variants/answers.toml")


class ConfigError(ValueError):
    """The benchmark config file is missing, malformed, or inconsistent."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RoleSettings:
    """One LLM role (builder or judge panel member) behind headless_llm."""

    provider: str
    model: str | None = None
    effort: str | None = None
    binary: str | None = None

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            choices = ", ".join(PROVIDERS)
            raise ConfigError(f"unknown provider {self.provider!r}; choose one of: {choices}")

    @property
    def identity(self) -> str:
        return f"{self.provider}:{self.model or 'default'}"


@dataclass(frozen=True, slots=True, kw_only=True)
class BuilderSettings(RoleSettings):
    timeout_seconds: float = 1800.0
    # None lets the provider keep its native default (required for codex,
    # whose app-server API has no per-run allow-list).
    allowed_tools: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class JudgeSettings:
    """Blind pairwise judging: every panel member sees both presentation orders."""

    panel: tuple[RoleSettings, ...]
    timeout_seconds: float = 900.0
    max_bundle_chars: int = 400_000
    max_file_chars: int = 40_000
    # Applied identically to both candidates; keeps the judge on the
    # application deliverable instead of repository infrastructure, which the
    # quantitative metrics already cover. Files the builder itself created or
    # modified are always shown, exclusions notwithstanding: only pristine
    # scaffolding may be hidden.
    exclude: tuple[str, ...] = ()
    # Case-insensitive literals blanked out of every bundle before judging:
    # provenance strings that would tell the judge a template exists.
    redact: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.panel:
            raise ConfigError("judge.panel must contain at least one member")
        if self.max_bundle_chars <= 0 or self.max_file_chars <= 0:
            raise ConfigError("judge bundle limits must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProbeSpec:
    """One functional acceptance command, run with argv (never a shell).

    `argv` items may reference `{db}` (per-run scratch database path), `{ws}`
    (workspace path), and variables captured by earlier probes. Probes run in
    declaration order and share state through `{db}` and captures.
    """

    name: str
    argv: tuple[str, ...]
    expect_exit: int = 0
    stdout_regex: str | None = None
    stderr_regex: str | None = None
    # (variable name, regex with one capture group) applied to stdout.
    capture: tuple[tuple[str, str], ...] = ()
    timeout_seconds: float = 180.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ConfigError("probe name must not be blank")
        if not self.argv:
            raise ConfigError(f"probe {self.name!r}: argv must not be empty")
        for pattern in (self.stdout_regex, self.stderr_regex):
            if pattern is not None:
                _compile(pattern, probe=self.name)
        for variable, pattern in self.capture:
            if not variable.isidentifier():
                raise ConfigError(f"probe {self.name!r}: capture name {variable!r} is invalid")
            if variable in ("db", "ws"):
                raise ConfigError(
                    f"probe {self.name!r}: capture name {variable!r} would shadow a "
                    "built-in scenario placeholder"
                )
            if _compile(pattern, probe=self.name).groups < 1:
                raise ConfigError(
                    f"probe {self.name!r}: capture regex {pattern!r} needs one group"
                )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScenarioPhase:
    """One post-build scenario phase with its own request and probe battery."""

    spec_text: str
    probes: tuple[ProbeSpec, ...]

    def __post_init__(self) -> None:
        if len(self.spec_text.strip()) < _MIN_SPEC_CHARS:
            raise ConfigError("maintenance spec text is suspiciously short")
        if not self.probes:
            raise ConfigError("maintenance phase requires at least one functional probe")


def _compile(pattern: str, *, probe: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as error:
        raise ConfigError(f"probe {probe!r}: invalid regex {pattern!r}: {error}") from error


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolPins:
    """Pinned neutral analyzers, invoked via `uvx tool==pin` for both arms."""

    ruff: str
    basedpyright: str
    radon: str
    coverage: str
    ruff_select: str = "F,E,W,B"
    ruff_ignore: str = "E501"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectSettings:
    name: str
    package: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TemplateSettings:
    vcs_ref: str = "HEAD"
    variant: str = "baseline"
    answers: dict[str, object]


@dataclass(frozen=True, slots=True, kw_only=True)
class RunSettings:
    # Out-of-tree by default: the pack forbids generated repositories inside
    # its own working tree.
    output_root: Path
    label: str
    seed: int = 0
    keep_workspaces: bool = True
    run_native_gate: bool = True
    # Both arms are independent until judging, so they run concurrently by
    # default; disable when provider rate limits or machine load require it.
    parallel_arms: bool = True
    headless_llm_path: Path = Path("../../headless_llm")
    install_timeout_seconds: float = 600.0
    tests_timeout_seconds: float = 600.0
    gate_timeout_seconds: float = 1200.0


@dataclass(frozen=True, slots=True, kw_only=True)
class LangfuseSettings:
    """Optional post-run export; disabled unless a config opts in."""

    enabled: bool = False
    base_url: str = "http://127.0.0.1:3000"
    public_key_env: str = "LANGFUSE_PUBLIC_KEY"
    secret_key_env: str = "LANGFUSE_SECRET_KEY"
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ConfigError("[langfuse]: base_url must start with http:// or https://")
        if self.timeout_seconds <= 0:
            raise ConfigError("[langfuse]: timeout_seconds must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkConfig:
    source_path: Path
    run: RunSettings
    project: ProjectSettings
    template: TemplateSettings
    builder: BuilderSettings
    judge: JudgeSettings
    probes: tuple[ProbeSpec, ...]
    tools: ToolPins
    spec_text: str
    charter_text: str
    langfuse: LangfuseSettings = field(default_factory=LangfuseSettings)
    maintenance: ScenarioPhase | None = None
    # Populated only by the campaign runner. The single-run config format and
    # pipeline stay unchanged, while manifests and registry rows can retain
    # the complete cell identity needed for resume.
    matrix_dimensions: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if len(self.spec_text.strip()) < _MIN_SPEC_CHARS:
            raise ConfigError("spec text is suspiciously short; refusing to benchmark it")
        if not self.charter_text.strip():
            raise ConfigError("charter text must not be blank")
        if not self.probes:
            raise ConfigError("at least one functional probe is required")


def _table(raw: dict[str, object], key: str, *, where: str) -> dict[str, object]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: missing required table [{key}]")
    return value


def _reject_unknown(section: dict[str, object], allowed: frozenset[str], *, where: str) -> None:
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown keys {unknown}; allowed: {sorted(allowed)}")


def _string(section: dict[str, object], key: str, *, where: str, default: str | None = None) -> str:
    value = section.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: {key!r} must be a non-empty string")
    return value.strip()


def _optional_string(section: dict[str, object], key: str, *, where: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{where}: {key!r} must be a string when present")
    return value.strip() or None


def _number(
    section: dict[str, object], key: str, *, where: str, default: float
) -> float:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where}: {key!r} must be a number")
    return float(value)


def _integer(section: dict[str, object], key: str, *, where: str, default: int) -> int:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{where}: {key!r} must be an integer")
    return value


def _boolean(section: dict[str, object], key: str, *, where: str, default: bool) -> bool:
    value = section.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{where}: {key!r} must be a boolean")
    return value


def _string_tuple(
    section: dict[str, object], key: str, *, where: str, default: tuple[str, ...] | None
) -> tuple[str, ...] | None:
    value = section.get(key)
    if value is None:
        return default
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{where}: {key!r} must be an array of strings")
    return tuple(value)


def _role(section: dict[str, object], *, where: str) -> RoleSettings:
    _reject_unknown(section, frozenset({"provider", "model", "effort", "binary"}), where=where)
    try:
        return RoleSettings(
            provider=_string(section, "provider", where=where),
            model=_optional_string(section, "model", where=where),
            effort=_optional_string(section, "effort", where=where),
            binary=_optional_string(section, "binary", where=where),
        )
    except ConfigError:
        raise
    except ValueError as error:
        raise ConfigError(f"{where}: {error}") from error


def _builder(section: dict[str, object], *, where: str) -> BuilderSettings:
    allowed = frozenset(
        {"provider", "model", "effort", "binary", "timeout_seconds", "allowed_tools"}
    )
    _reject_unknown(section, allowed, where=where)
    return BuilderSettings(
        provider=_string(section, "provider", where=where),
        model=_optional_string(section, "model", where=where),
        effort=_optional_string(section, "effort", where=where),
        binary=_optional_string(section, "binary", where=where),
        timeout_seconds=_number(section, "timeout_seconds", where=where, default=1800.0),
        allowed_tools=_string_tuple(section, "allowed_tools", where=where, default=None),
    )


def _judge(section: dict[str, object], *, where: str) -> JudgeSettings:
    allowed = frozenset(
        {"panel", "timeout_seconds", "max_bundle_chars", "max_file_chars", "exclude", "redact"}
    )
    _reject_unknown(section, allowed, where=where)
    raw_panel = section.get("panel")
    if not isinstance(raw_panel, list) or not raw_panel:
        raise ConfigError(f"{where}: 'panel' must be a non-empty array of tables")
    panel: list[RoleSettings] = []
    for index, member in enumerate(raw_panel):
        member_where = f"{where}.panel[{index}]"
        if not isinstance(member, dict):
            raise ConfigError(f"{member_where}: must be a table")
        panel.append(_role(member, where=member_where))
    return JudgeSettings(
        panel=tuple(panel),
        timeout_seconds=_number(section, "timeout_seconds", where=where, default=900.0),
        max_bundle_chars=_integer(section, "max_bundle_chars", where=where, default=400_000),
        max_file_chars=_integer(section, "max_file_chars", where=where, default=40_000),
        exclude=_string_tuple(section, "exclude", where=where, default=()) or (),
        redact=_string_tuple(section, "redact", where=where, default=()) or (),
    )


def _probe(section: dict[str, object], *, where: str) -> ProbeSpec:
    allowed = frozenset(
        {
            "name",
            "argv",
            "expect_exit",
            "stdout_regex",
            "stderr_regex",
            "capture",
            "timeout_seconds",
        }
    )
    _reject_unknown(section, allowed, where=where)
    argv = _string_tuple(section, "argv", where=where, default=None)
    if argv is None:
        raise ConfigError(f"{where}: 'argv' is required")
    raw_capture = section.get("capture", [])
    if not isinstance(raw_capture, list):
        raise ConfigError(f"{where}: 'capture' must be an array of [name, regex] pairs")
    capture: list[tuple[str, str]] = []
    for pair in raw_capture:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(item, str) for item in pair)
        ):
            raise ConfigError(f"{where}: 'capture' entries must be [name, regex] string pairs")
        capture.append((pair[0], pair[1]))
    return ProbeSpec(
        name=_string(section, "name", where=where),
        argv=argv,
        expect_exit=_integer(section, "expect_exit", where=where, default=0),
        stdout_regex=_optional_string(section, "stdout_regex", where=where),
        stderr_regex=_optional_string(section, "stderr_regex", where=where),
        capture=tuple(capture),
        timeout_seconds=_number(section, "timeout_seconds", where=where, default=180.0),
    )


def _tools(section: dict[str, object], *, where: str) -> ToolPins:
    allowed = frozenset(
        {"ruff", "basedpyright", "radon", "coverage", "ruff_select", "ruff_ignore"}
    )
    _reject_unknown(section, allowed, where=where)
    return ToolPins(
        ruff=_string(section, "ruff", where=where),
        basedpyright=_string(section, "basedpyright", where=where),
        radon=_string(section, "radon", where=where),
        coverage=_string(section, "coverage", where=where),
        ruff_select=_string(section, "ruff_select", where=where, default="F,E,W,B"),
        ruff_ignore=_string(section, "ruff_ignore", where=where, default="E501"),
    )


def _run(section: dict[str, object], *, where: str, repo_root: Path) -> RunSettings:
    allowed = frozenset(
        {
            "output_root",
            "label",
            "seed",
            "keep_workspaces",
            "run_native_gate",
            "parallel_arms",
            "headless_llm_path",
            "install_timeout_seconds",
            "tests_timeout_seconds",
            "gate_timeout_seconds",
        }
    )
    _reject_unknown(section, allowed, where=where)
    output_root = Path(_string(section, "output_root", where=where)).expanduser()
    if not output_root.is_absolute():
        output_root = (repo_root / output_root).resolve()
    if output_root.resolve().is_relative_to(repo_root.resolve()):
        raise ConfigError(
            f"{where}: output_root {output_root} is inside the pack working tree; "
            "generated repositories must stay out of the tree"
        )
    headless = Path(
        _string(section, "headless_llm_path", where=where, default="../../headless_llm")
    ).expanduser()
    if not headless.is_absolute():
        headless = (repo_root / headless).resolve()
    return RunSettings(
        output_root=output_root,
        label=_string(section, "label", where=where),
        seed=_integer(section, "seed", where=where, default=0),
        keep_workspaces=_boolean(section, "keep_workspaces", where=where, default=True),
        run_native_gate=_boolean(section, "run_native_gate", where=where, default=True),
        parallel_arms=_boolean(section, "parallel_arms", where=where, default=True),
        headless_llm_path=headless,
        install_timeout_seconds=_number(
            section, "install_timeout_seconds", where=where, default=600.0
        ),
        tests_timeout_seconds=_number(
            section, "tests_timeout_seconds", where=where, default=600.0
        ),
        gate_timeout_seconds=_number(
            section, "gate_timeout_seconds", where=where, default=1200.0
        ),
    )


def _project(section: dict[str, object], *, where: str) -> ProjectSettings:
    _reject_unknown(section, frozenset({"name", "package"}), where=where)
    name = _string(section, "name", where=where)
    package = _string(section, "package", where=where, default=name.replace("-", "_"))
    return ProjectSettings(name=name, package=package)


def _template_variants(repo_root: Path) -> dict[str, dict[str, object]]:
    path = repo_root / _VARIANT_ANSWERS
    try:
        raw: dict[str, object] = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"template variant answer sets not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: invalid TOML: {error}") from error

    variants: dict[str, dict[str, object]] = {}
    for name, answers in raw.items():
        if not isinstance(answers, dict):
            raise ConfigError(f"{path}: variant {name!r} must be a table of Copier answers")
        variants[name] = dict(answers)
    return variants


def template_variant_answers(
    name: str, *, where: str, repo_root: Path
) -> dict[str, object]:
    """Return a copy of a named Copier answer set, or reject it eagerly."""
    variants = _template_variants(repo_root)
    try:
        return dict(variants[name])
    except KeyError as error:
        known = ", ".join(sorted(variants))
        raise ConfigError(
            f"{where}: unknown template variant {name!r}; known variants: {known}"
        ) from error


def _template(
    section: dict[str, object], *, where: str, repo_root: Path
) -> TemplateSettings:
    _reject_unknown(section, frozenset({"vcs_ref", "variant", "answers"}), where=where)
    answers = section.get("answers", {})
    if not isinstance(answers, dict):
        raise ConfigError(f"{where}: 'answers' must be a table")
    variant = _string(section, "variant", where=where, default="baseline")
    variants = _template_variants(repo_root)
    if variant not in variants:
        known = ", ".join(sorted(variants))
        raise ConfigError(
            f"{where}: unknown template variant {variant!r}; known variants: {known}"
        )
    variant_answers = variants[variant]
    feature_toggles = {
        key
        for name, answer_set in variants.items()
        if name != "baseline"
        for key in answer_set
    }
    for key in answers:
        if key in feature_toggles and key not in variant_answers:
            raise ConfigError(
                f"{where}: feature-toggle answer {key!r} is owned by an ablation; "
                "select its named variant instead of setting it in [template.answers]"
            )
    for key, value in variant_answers.items():
        if key in answers and answers[key] != value:
            declared = str(value).lower() if isinstance(value, bool) else repr(value)
            override = (
                str(answers[key]).lower()
                if isinstance(answers[key], bool)
                else repr(answers[key])
            )
            raise ConfigError(
                f"{where}: variant {variant!r} answer {key!r} declares {declared}; "
                f"[template.answers] cannot override it with {override}"
            )
    resolved_answers = {**variant_answers, **answers}
    return TemplateSettings(
        vcs_ref=_string(section, "vcs_ref", where=where, default="HEAD"),
        variant=variant,
        answers=resolved_answers,
    )


def _langfuse(section: dict[str, object], *, where: str) -> LangfuseSettings:
    _reject_unknown(
        section,
        frozenset(
            {
                "enabled",
                "base_url",
                "public_key_env",
                "secret_key_env",
                "timeout_seconds",
            }
        ),
        where=where,
    )
    return LangfuseSettings(
        enabled=_boolean(section, "enabled", where=where, default=False),
        base_url=_string(
            section, "base_url", where=where, default="http://127.0.0.1:3000"
        ).rstrip("/"),
        public_key_env=_string(
            section, "public_key_env", where=where, default="LANGFUSE_PUBLIC_KEY"
        ),
        secret_key_env=_string(
            section, "secret_key_env", where=where, default="LANGFUSE_SECRET_KEY"
        ),
        timeout_seconds=_number(section, "timeout_seconds", where=where, default=5.0),
    )


def _prompt_text(section: dict[str, object], key: str, *, where: str, config_dir: Path) -> str:
    path = Path(_string(section, key, where=where))
    if not path.is_absolute():
        path = config_dir / path
    if not path.is_file():
        raise ConfigError(f"{where}: {key} file not found: {path}")
    return path.read_text(encoding="utf-8")


def _scenario(
    section: object,
    *,
    where: str,
    config_dir: Path,
) -> ScenarioPhase | None:
    if section is None:
        return None
    if not isinstance(section, dict):
        raise ConfigError(f"{where}: [scenario] must be a table")
    _reject_unknown(section, frozenset({"maintenance"}), where=where)
    maintenance = _table(section, "maintenance", where=where)
    maintenance_where = f"{where}.maintenance"
    _reject_unknown(
        maintenance,
        frozenset({"spec_file", "probes"}),
        where=maintenance_where,
    )
    raw_probes = maintenance.get("probes")
    if not isinstance(raw_probes, list):
        raise ConfigError(
            f"{maintenance_where}: [[scenario.maintenance.probes]] must be an array of tables"
        )
    probes: list[ProbeSpec] = []
    for index, entry in enumerate(raw_probes):
        probe_where = f"{maintenance_where}.probes[{index}]"
        if not isinstance(entry, dict):
            raise ConfigError(f"{probe_where}: must be a table")
        probes.append(_probe(entry, where=probe_where))
    return ScenarioPhase(
        spec_text=_prompt_text(
            maintenance,
            "spec_file",
            where=maintenance_where,
            config_dir=config_dir,
        ),
        probes=tuple(probes),
    )


# Convenience aliases for the builder-model override; anything not listed is
# passed through verbatim (full model ids, provider-native names).
BUILDER_MODEL_ALIASES = {
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
    "haiku": "claude-haiku-4-5-20251001",
}


def apply_builder_overrides(
    cfg: BenchmarkConfig,
    *,
    provider: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> BenchmarkConfig:
    """Command-line builder overrides on top of the loaded config.

    The TOML file stays the reproducible record; these exist so `just
    benchmark` can vary the coding model or provider without editing it. The
    resolved identity lands in the run manifest either way. Switching away
    from claude drops the claude-specific `allowed_tools` list and any
    `binary` override: codex has no per-run allow-list and opencode checks
    tool names against its own registry, so each provider falls back to its
    native defaults.
    """
    if provider is None and model is None and effort is None:
        return cfg
    builder = cfg.builder
    new_provider = provider or builder.provider
    resolved_model = BUILDER_MODEL_ALIASES.get(model, model) if model else builder.model
    return replace(
        cfg,
        builder=BuilderSettings(
            provider=new_provider,
            model=resolved_model,
            effort=effort or builder.effort,
            binary=builder.binary if new_provider == builder.provider else None,
            timeout_seconds=builder.timeout_seconds,
            allowed_tools=builder.allowed_tools if new_provider == "claude" else None,
        ),
    )


def load_config(path: Path, *, repo_root: Path) -> BenchmarkConfig:
    """Parse and validate a benchmark config file. Raises ConfigError on any problem."""
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw: dict[str, object] = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: invalid TOML: {error}") from error

    where = str(path)
    _reject_unknown(
        raw,
        frozenset(
            {
                "run",
                "project",
                "template",
                "builder",
                "judge",
                "prompt",
                "probes",
                "tools",
                "langfuse",
                "scenario",
            }
        ),
        where=where,
    )
    prompt_section = _table(raw, "prompt", where=where)
    _reject_unknown(prompt_section, frozenset({"spec_file", "charter_file"}), where=where)

    raw_probes = raw.get("probes")
    if not isinstance(raw_probes, list):
        raise ConfigError(f"{where}: [[probes]] must be an array of tables")
    probes: list[ProbeSpec] = []
    for index, entry in enumerate(raw_probes):
        if not isinstance(entry, dict):
            raise ConfigError(f"{where}: probes[{index}] must be a table")
        probes.append(_probe(entry, where=f"{where}: probes[{index}]"))

    raw_langfuse = raw.get("langfuse", {})
    if not isinstance(raw_langfuse, dict):
        raise ConfigError(f"{where}: [langfuse] must be a table")

    return BenchmarkConfig(
        source_path=path.resolve(),
        run=_run(_table(raw, "run", where=where), where=f"{where}: [run]", repo_root=repo_root),
        project=_project(_table(raw, "project", where=where), where=f"{where}: [project]"),
        template=_template(
            _table(raw, "template", where=where),
            where=f"{where}: [template]",
            repo_root=repo_root,
        ),
        builder=_builder(_table(raw, "builder", where=where), where=f"{where}: [builder]"),
        judge=_judge(_table(raw, "judge", where=where), where=f"{where}: [judge]"),
        probes=tuple(probes),
        tools=_tools(_table(raw, "tools", where=where), where=f"{where}: [tools]"),
        spec_text=_prompt_text(
            prompt_section, "spec_file", where=f"{where}: [prompt]", config_dir=path.parent
        ),
        charter_text=_prompt_text(
            prompt_section, "charter_file", where=f"{where}: [prompt]", config_dir=path.parent
        ),
        langfuse=_langfuse(raw_langfuse, where=f"{where}: [langfuse]"),
        maintenance=_scenario(
            raw.get("scenario"),
            where=f"{where}: [scenario]",
            config_dir=path.parent,
        ),
    )
