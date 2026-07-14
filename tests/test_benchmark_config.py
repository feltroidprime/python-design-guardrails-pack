"""Configuration contract of the end-to-end value benchmark.

The shipped configs must stay loadable and keep their fairness properties
(cross-family judge panel, out-of-tree output) without running any LLM.
"""

from pathlib import Path

import pytest

from benchmarks.e2e.config import (
    ConfigError,
    apply_builder_overrides,
    load_config,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "benchmarks" / "config"


def _write_config(tmp_path: Path, body: str) -> Path:
    (tmp_path / "spec.md").write_text("spec " * 60, encoding="utf-8")
    (tmp_path / "change.md").write_text("change request " * 40, encoding="utf-8")
    (tmp_path / "charter.md").write_text("charter", encoding="utf-8")
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


_MINIMAL = """
[run]
output_root = "{output_root}"
label = "test"

[project]
name = "demo"

[template]
{template}

[builder]
provider = "claude"

[judge]
[[judge.panel]]
provider = "codex"

[prompt]
spec_file = "spec.md"
charter_file = "charter.md"

[tools]
ruff = "1"
basedpyright = "1"
radon = "1"
coverage = "1"

[[probes]]
name = "noop"
argv = ["true"]
{extra}
"""


def _minimal(
    tmp_path: Path,
    *,
    output_root: str | None = None,
    template: str = "",
    extra: str = "",
) -> Path:
    root = output_root or str(tmp_path / "runs")
    return _write_config(
        tmp_path,
        _MINIMAL.format(output_root=root, template=template, extra=extra),
    )


class TestShippedConfigs:
    @pytest.mark.parametrize("path", sorted(CONFIG_DIR.glob("*.toml")), ids=lambda path: path.name)
    def test_every_shipped_config_loads(self, path: Path) -> None:
        cfg = load_config(path, repo_root=REPO_ROOT)
        assert cfg.probes
        assert cfg.judge.panel

    def test_real_app_configs_include_relay(self) -> None:
        assert (CONFIG_DIR / "relay.toml").is_file()

    @pytest.mark.parametrize("name", ("default.toml", "relay.toml"))
    def test_real_app_configs_define_a_maintenance_phase(self, name: str) -> None:
        cfg = load_config(CONFIG_DIR / name, repo_root=REPO_ROOT)

        assert cfg.maintenance is not None
        assert len(cfg.maintenance.spec_text) >= 200
        assert cfg.maintenance.probes

    def test_default_probes_cover_error_paths_too(self) -> None:
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        assert len(cfg.probes) >= 10
        assert any(probe.expect_exit != 0 for probe in cfg.probes)

    def test_maintenance_probes_cover_custom_and_invalid_intervals(self) -> None:
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        assert cfg.maintenance is not None
        probes = {probe.name: probe for probe in cfg.maintenance.probes}

        assert probes["invalid-recurring-interval-is-rejected"].expect_exit == 2
        assert probes["add-two-month-recurring-rule"].argv[-2:] == (
            "--interval-months",
            "2",
        )
        assert "custom-interval-skips-june" in probes
        assert "custom-interval-resumes-in-july" in probes

    def test_relay_maintenance_probes_reject_mixed_json_schemas(self) -> None:
        cfg = load_config(CONFIG_DIR / "relay.toml", repo_root=REPO_ROOT)
        assert cfg.maintenance is not None
        probes = {probe.name: probe for probe in cfg.maintenance.probes}

        assert probes["mixed-json-schemas-are-rejected"].expect_exit == 2
        assert "mixed-json-rejection-appends-nothing" in probes

    def test_default_judge_panel_shares_no_family_with_builder(self) -> None:
        """Anti-bias regression: no judge may come from the builder's provider."""
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        assert all(member.provider != cfg.builder.provider for member in cfg.judge.panel)
        assert len(cfg.judge.panel) >= 2

    def test_default_output_root_is_out_of_tree(self) -> None:
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        assert not cfg.run.output_root.is_relative_to(REPO_ROOT)

    @pytest.mark.parametrize("path", sorted(CONFIG_DIR.glob("*.toml")), ids=lambda path: path.name)
    def test_every_shipped_judge_excludes_copier_answers(self, path: Path) -> None:
        cfg = load_config(path, repo_root=REPO_ROOT)
        assert ".copier-answers.yml" in cfg.judge.exclude


class TestValidation:
    def test_minimal_config_loads(self, tmp_path: Path) -> None:
        cfg = load_config(_minimal(tmp_path), repo_root=REPO_ROOT)
        assert cfg.project.package == "demo"
        assert cfg.builder.allowed_tools is None
        assert cfg.maintenance is None

    def test_maintenance_phase_is_typed_and_unknown_keys_are_rejected(
        self, tmp_path: Path
    ) -> None:
        scenario = '''
[scenario.maintenance]
spec_file = "change.md"

[[scenario.maintenance.probes]]
name = "changed"
argv = ["true"]
'''
        cfg = load_config(_minimal(tmp_path, extra=scenario), repo_root=REPO_ROOT)

        assert cfg.maintenance is not None
        assert cfg.maintenance.spec_text == "change request " * 40
        assert [probe.name for probe in cfg.maintenance.probes] == ["changed"]

        bad = scenario.replace('argv = ["true"]', 'argv = ["true"]\nunknown = 1')
        with pytest.raises(ConfigError, match=r"maintenance.*probes.*unknown"):
            load_config(_minimal(tmp_path, extra=bad), repo_root=REPO_ROOT)

    def test_template_settings_and_answer_overrides_are_parsed(
        self, tmp_path: Path
    ) -> None:
        path = _minimal(
            tmp_path,
            template='vcs_ref = "v1.2.3"\nvariant = "baseline"\nanswers = { feature = true }',
        )

        cfg = load_config(path, repo_root=REPO_ROOT)

        assert cfg.template.vcs_ref == "v1.2.3"
        assert cfg.template.variant == "baseline"
        assert cfg.template.answers == {"feature": True}

    def test_langfuse_export_settings_are_parsed(self, tmp_path: Path) -> None:
        path = _minimal(
            tmp_path,
            extra="""
[langfuse]
enabled = true
base_url = "http://127.0.0.1:3000"
public_key_env = "BENCHMARK_LANGFUSE_PUBLIC_KEY"
secret_key_env = "BENCHMARK_LANGFUSE_SECRET_KEY"
timeout_seconds = 2.5
""",
        )

        cfg = load_config(path, repo_root=REPO_ROOT)

        assert cfg.langfuse.enabled is True
        assert cfg.langfuse.base_url == "http://127.0.0.1:3000"
        assert cfg.langfuse.public_key_env == "BENCHMARK_LANGFUSE_PUBLIC_KEY"
        assert cfg.langfuse.secret_key_env == "BENCHMARK_LANGFUSE_SECRET_KEY"
        assert cfg.langfuse.timeout_seconds == 2.5

    def test_unknown_langfuse_key_is_rejected(self, tmp_path: Path) -> None:
        path = _minimal(
            tmp_path,
            extra="\n[langfuse]\nenabled = true\nendpoint_typo = 'nope'\n",
        )

        with pytest.raises(ConfigError, match="endpoint_typo"):
            load_config(path, repo_root=REPO_ROOT)

    def test_langfuse_must_be_a_table(self, tmp_path: Path) -> None:
        body = _MINIMAL.format(
            output_root=str(tmp_path / "runs"), template="", extra=""
        ).replace("[run]", "langfuse = true\n\n[run]", 1)
        path = _write_config(tmp_path, body)

        with pytest.raises(ConfigError, match="langfuse.*table"):
            load_config(path, repo_root=REPO_ROOT)

    def test_unknown_template_key_is_rejected(self, tmp_path: Path) -> None:
        path = _minimal(tmp_path, template="version_typo = 'v1.2.3'")

        with pytest.raises(ConfigError, match="version_typo"):
            load_config(path, repo_root=REPO_ROOT)

    @pytest.mark.parametrize(
        ("variant", "answers"),
        (
            ("no-precommit", {"precommit": False}),
            ("no-agents-md", {"agents_contract": "none"}),
            ("checks-via-commit", {"agents_contract": "hooks-first"}),
        ),
    )
    def test_named_variant_resolves_its_answer_set(
        self, tmp_path: Path, variant: str, answers: dict[str, object]
    ) -> None:
        path = _minimal(tmp_path, template=f"variant = {variant!r}")

        cfg = load_config(path, repo_root=REPO_ROOT)

        assert cfg.template.variant == variant
        assert cfg.template.answers == answers

    def test_unknown_variant_lists_every_known_name(self, tmp_path: Path) -> None:
        path = _minimal(tmp_path, template="variant = 'missing-ablation'")

        with pytest.raises(ConfigError) as raised:
            load_config(path, repo_root=REPO_ROOT)

        assert str(raised.value) == (
            f"{path}: [template]: unknown template variant 'missing-ablation'; "
            "known variants: baseline, checks-via-commit, no-agents-md, no-precommit"
        )

    def test_variant_answer_cannot_be_overridden(self, tmp_path: Path) -> None:
        path = _minimal(
            tmp_path,
            template="variant = 'no-precommit'\nanswers = { precommit = true }",
        )

        with pytest.raises(
            ConfigError,
            match="no-precommit.*precommit.*declares false.*override.*true",
        ):
            load_config(path, repo_root=REPO_ROOT)

    @pytest.mark.parametrize(
        "template",
        (
            "answers = { precommit = false }",
            "variant = 'checks-via-commit'\nanswers = { precommit = false }",
        ),
    )
    def test_feature_toggles_require_their_named_variant(
        self, tmp_path: Path, template: str
    ) -> None:
        path = _minimal(tmp_path, template=template)

        with pytest.raises(
            ConfigError,
            match="feature-toggle answer 'precommit'.*select its named variant",
        ):
            load_config(path, repo_root=REPO_ROOT)

    def test_unknown_key_is_rejected(self, tmp_path: Path) -> None:
        path = _minimal(tmp_path, extra="\n[typo_section]\nx = 1\n")
        with pytest.raises(ConfigError, match="typo_section"):
            load_config(path, repo_root=REPO_ROOT)

    def test_output_root_inside_tree_is_rejected(self, tmp_path: Path) -> None:
        path = _minimal(tmp_path, output_root=str(REPO_ROOT / "benchmarks" / "runs"))
        with pytest.raises(ConfigError, match="working tree"):
            load_config(path, repo_root=REPO_ROOT)

    def test_unknown_provider_is_rejected(self, tmp_path: Path) -> None:
        body = _MINIMAL.format(
            output_root=str(tmp_path / "runs"), template="", extra=""
        ).replace(
            'provider = "claude"', 'provider = "gpt4all"'
        )
        with pytest.raises(ConfigError, match="unknown provider"):
            load_config(_write_config(tmp_path, body), repo_root=REPO_ROOT)

    def test_capture_regex_without_group_is_rejected(self, tmp_path: Path) -> None:
        extra = '\n[[probes]]\nname = "bad"\nargv = ["true"]\ncapture = [["ident", "id=."]]\n'
        with pytest.raises(ConfigError, match="needs one group"):
            load_config(_minimal(tmp_path, extra=extra), repo_root=REPO_ROOT)

    def test_capture_name_shadowing_builtin_placeholder_is_rejected(
        self, tmp_path: Path
    ) -> None:
        extra = '\n[[probes]]\nname = "bad"\nargv = ["true"]\ncapture = [["db", "(x)"]]\n'
        with pytest.raises(ConfigError, match="shadow"):
            load_config(_minimal(tmp_path, extra=extra), repo_root=REPO_ROOT)

    def test_missing_spec_file_is_rejected(self, tmp_path: Path) -> None:
        path = _minimal(tmp_path)
        (tmp_path / "spec.md").unlink()
        with pytest.raises(ConfigError, match="spec_file"):
            load_config(path, repo_root=REPO_ROOT)


class TestBuilderOverrides:
    def test_no_override_returns_config_unchanged(self) -> None:
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        assert apply_builder_overrides(cfg) is cfg

    def test_model_alias_resolves_and_keeps_the_rest(self) -> None:
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        overridden = apply_builder_overrides(cfg, model="haiku")
        assert overridden.builder.model == "claude-haiku-4-5-20251001"
        assert overridden.builder.provider == cfg.builder.provider
        assert overridden.builder.allowed_tools == cfg.builder.allowed_tools
        assert overridden.builder.timeout_seconds == cfg.builder.timeout_seconds

    def test_unknown_model_passes_through_verbatim(self) -> None:
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        assert apply_builder_overrides(cfg, model="my-model-id").builder.model == "my-model-id"

    def test_provider_switch_drops_claude_specific_settings(self) -> None:
        """Codex has no per-run tool allow-list; keeping one would crash the run."""
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        overridden = apply_builder_overrides(cfg, provider="codex", model="gpt-5.6-sol")
        assert overridden.builder.provider == "codex"
        assert overridden.builder.allowed_tools is None
        assert overridden.builder.binary is None

    def test_effort_only_override(self) -> None:
        cfg = load_config(CONFIG_DIR / "default.toml", repo_root=REPO_ROOT)
        overridden = apply_builder_overrides(cfg, effort="medium")
        assert overridden.builder.effort == "medium"
        assert overridden.builder.model == cfg.builder.model
