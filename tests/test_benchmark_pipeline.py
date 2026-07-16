"""Deterministic pipeline tests for the value benchmark: no network, no LLM.

The full orchestration runs against a fake agent runner, which also proves the
central fairness invariant mechanically: both arms receive the identical
build prompt.
"""

from dataclasses import replace
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
from yaml import safe_load

from benchmarks.e2e import events as ev
from benchmarks.e2e.agents import AgentOutcome
from benchmarks.e2e.config import (
    ARM_BARE,
    ARM_GUARDRAILS,
    ARMS,
    BenchmarkConfig,
    BuilderSettings,
    JudgeSettings,
    ProbeSpec,
    ProjectSettings,
    RoleSettings,
    RunSettings,
    ScenarioPhase,
    TemplateSettings,
    ToolPins,
    load_config,
)
from benchmarks.e2e.judging import (
    DIMENSIONS,
    JudgingError,
    aggregate_judgments,
    assignments_for_seed,
    bundle_workspace,
    judge_prompt_static_text,
    parse_judgment,
)
from benchmarks.e2e.metrics import (
    loc_summary,
    parse_basedpyright_output,
    parse_coverage_json,
    parse_pytest_summary,
    parse_radon_cc_output,
    parse_ruff_output,
    python_files,
)
from benchmarks.e2e.orchestrator import compose_build_prompt, run_benchmark
from benchmarks.e2e.probes import pass_rate, run_probes
from benchmarks.e2e.reporting import render_report
from benchmarks.e2e.workspaces import git_environment, prepare_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]


def _outcome(structured: object = None, text: str = "done") -> AgentOutcome:
    return AgentOutcome(
        text=text,
        structured=structured,
        model="fake-model",
        duration_ms=1200,
        turns=3,
        tool_calls=5,
        input_tokens=100,
        output_tokens=50,
        reasoning_tokens=25,
        cached_input_tokens=0,
        cost_usd=0.01,
        cost_provenance="computed",
    )


def _judge_payload(preference: str = "a") -> dict[str, object]:
    scores = {dimension: 7 for dimension in DIMENSIONS}
    return {
        "candidate_a": {**scores, "top_risk": "risk a"},
        "candidate_b": {**scores, "domain_and_invariants": 5, "top_risk": "risk b"},
        "preference": preference,
        "preference_strength": "clear",
        "rationale": "cites files",
    }


class TestProbes:
    def test_scenario_with_captures_and_placeholders(self, tmp_path: Path) -> None:
        probes = (
            ProbeSpec(
                name="emit-id",
                argv=(sys.executable, "-c", "print('id=41')"),
                stdout_regex=r"(?m)^id=\d+$",
                capture=(("ident", r"id=(\d+)"),),
            ),
            ProbeSpec(
                name="reuse-capture",
                argv=(sys.executable, "-c", "import sys; sys.exit(0 if '{ident}' == '41' else 1)"),
            ),
            ProbeSpec(
                name="expected-failure-exit",
                argv=(sys.executable, "-c", "import sys; sys.exit(3)"),
                expect_exit=3,
            ),
        )
        results = run_probes(probes, tmp_path, tmp_path / "scratch")
        assert [result.passed for result in results] == [True, True, True]
        assert pass_rate(results) == 1.0

    def test_failures_are_recorded_not_raised(self, tmp_path: Path) -> None:
        probes = (
            ProbeSpec(name="wrong-exit", argv=(sys.executable, "-c", "raise SystemExit(1)")),
            ProbeSpec(name="unknown-placeholder", argv=("echo", "{never_captured}")),
            ProbeSpec(
                name="bad-output",
                argv=(sys.executable, "-c", "print('nope')"),
                stdout_regex=r"(?m)^yes$",
            ),
        )
        results = run_probes(probes, tmp_path, tmp_path / "scratch")
        assert [result.passed for result in results] == [False, False, False]
        assert results[0].failure is not None and "exit code 1" in results[0].failure
        assert results[1].failure is not None and "placeholder" in results[1].failure
        assert results[2].failure is not None and "stdout" in results[2].failure

    def test_timeout_is_a_failure(self, tmp_path: Path) -> None:
        probes = (
            ProbeSpec(
                name="sleepy",
                argv=(sys.executable, "-c", "import time; time.sleep(5)"),
                timeout_seconds=0.5,
            ),
        )
        results = run_probes(probes, tmp_path, tmp_path / "scratch")
        assert not results[0].passed
        assert results[0].failure is not None and "timed out" in results[0].failure


class TestMetricsParsers:
    def test_loc_scanner_splits_sources_and_tests(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / "src" / "app" / "core.py").write_text("x = 1\n\ny = 2\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_core.py").write_text("def test(): pass\n", encoding="utf-8")
        (tmp_path / "conftest.py").write_text("import sys\n", encoding="utf-8")
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "vendor.py").write_text("v = 1\n", encoding="utf-8")
        sources, tests = python_files(tmp_path)
        assert [path.name for path in sources] == ["core.py"]
        assert sorted(path.name for path in tests) == ["conftest.py", "test_core.py"]
        summary = loc_summary(tmp_path)
        assert summary == {
            "source_files": 1,
            "source_loc": 2,
            "test_files": 2,
            "test_loc": 2,
        }

    def test_ruff_output_parsing(self) -> None:
        stdout = '[{"code": "F401"}, {"code": "F401"}, {"code": "E711"}]'
        assert parse_ruff_output(stdout) == {
            "violations": 3,
            "by_code": {"F401": 2, "E711": 1},
            "parse_error": False,
        }
        assert parse_ruff_output("not json")["parse_error"] is True

    def test_basedpyright_output_parsing(self) -> None:
        stdout = '{"summary": {"errorCount": 4, "warningCount": 1, "filesAnalyzed": 9}}'
        parsed = parse_basedpyright_output(stdout)
        assert parsed["errors"] == 4
        assert parsed["warnings"] == 1

    def test_radon_output_parsing(self) -> None:
        stdout = (
            '{"a.py": [{"complexity": 1}, {"complexity": 5}],'
            ' "b.py": [{"complexity": 3}]}'
        )
        parsed = parse_radon_cc_output(stdout)
        assert parsed == {
            "blocks": 3,
            "average_complexity": 3.0,
            "max_complexity": 5,
            "parse_error": False,
        }

    def test_coverage_parsing_ignores_tests_and_venv(self, tmp_path: Path) -> None:
        text = (
            '{"files": {'
            '"app.py": {"summary": {"covered_lines": 8, "num_statements": 10}},'
            '"tests/test_app.py": {"summary": {"covered_lines": 5, "num_statements": 5}},'
            '".venv/lib/vendor.py": {"summary": {"covered_lines": 1, "num_statements": 50}}'
            "}}"
        )
        parsed = parse_coverage_json(text, tmp_path)
        assert parsed == {"percent": 80.0, "measured_files": 1, "parse_error": False}

    def test_coverage_parsing_applies_symmetric_app_scope(self, tmp_path: Path) -> None:
        """Repository infrastructure must not dilute the application figure."""
        text = (
            '{"files": {'
            '"src/app/core.py": {"summary": {"covered_lines": 9, "num_statements": 10}},'
            '"scripts/quality_gate.py": {"summary": {"covered_lines": 0, "num_statements": 90}}'
            "}}"
        )
        parsed = parse_coverage_json(text, tmp_path, app_exclude=("scripts/*",))
        assert parsed == {"percent": 90.0, "measured_files": 1, "parse_error": False}

    def test_pytest_summary_parsing(self) -> None:
        assert parse_pytest_summary("12 passed, 2 failed, 1 error in 3.21s") == {
            "passed": 12,
            "failed": 2,
            "error": 1,
        }

    def test_pytest_summary_ignores_nested_pytest_output(self) -> None:
        """Candidate tests that print pytest-like lines must not double-count."""
        stdout = (
            "subprocess said: 99 passed in 0.1s\n"
            "more noise\n"
            "===== 12 passed, 1 failed in 3.21s =====\n"
        )
        assert parse_pytest_summary(stdout) == {"passed": 12, "failed": 1}

    def test_python_files_applies_app_scope(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "guard.py").write_text("y = 2\n", encoding="utf-8")
        sources, _tests = python_files(tmp_path, app_exclude=("scripts/*",))
        assert [path.name for path in sources] == ["app.py"]
        summary = loc_summary(tmp_path, app_exclude=("scripts/*",))
        assert summary["source_files"] == 1


class TestJudging:
    def test_static_judge_framing_never_reveals_provenance(self) -> None:
        """The judge must not learn that a template or baseline exists."""
        text = judge_prompt_static_text().lower()
        for marker in (
            "template",
            "guardrail",
            "baseline",
            "scaffold",
            "with and without",
        ):
            assert re.search(rf"\b{re.escape(marker)}\b", text) is None, marker

    def test_real_template_bundle_carries_no_provenance(self, tmp_path: Path) -> None:
        """Regression for the audit's critical finding: an actually generated
        workspace, bundled with the shipped default judge settings, must not
        contain any pack-identifying marker. The fix lives in the template
        itself (no pack branding in generated files), so this must hold with
        no redaction configured."""
        import sys as _sys

        _sys.path.insert(0, str(REPO_ROOT))
        from instantiate import generate

        from benchmarks.e2e.config import load_config

        assert generate("ledger", "ledger", tmp_path / "ws") is None
        cfg = load_config(
            REPO_ROOT / "benchmarks" / "config" / "default.toml", repo_root=REPO_ROOT
        )
        assert cfg.judge.redact == (), "cleanliness must come from the template, not masking"
        bundle = bundle_workspace(tmp_path / "ws", cfg.judge)
        lowered = bundle.text.lower()
        for marker in (
            "guardrail",
            "template",
        ):
            assert marker not in lowered, f"provenance marker {marker!r} reached the judge"
        assert bundle.file_count > 0

    def test_redaction_is_case_insensitive_and_shape_preserving(self) -> None:
        from benchmarks.e2e.judging import redact_text

        text = "Uses the Guardrails pack and GUARDRAILS rules; guardrails-free code."
        redacted = redact_text(text, ("guardrails",))
        assert "guardrail" not in redacted.lower()
        assert redacted.count("▮▮▮") == 3

    def test_agent_authored_files_bypass_exclusions(self, tmp_path: Path) -> None:
        """Exclusions hide pristine scaffolding only; builder work is shown."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "template_note.md").write_text("boilerplate\n", encoding="utf-8")
        (tmp_path / "docs" / "adr-new.md").write_text("agent decision\n", encoding="utf-8")
        settings = JudgeSettings(
            panel=(RoleSettings(provider="codex"),), exclude=("docs/*",)
        )
        bundle = bundle_workspace(
            tmp_path, settings, changed_files=frozenset({"docs/adr-new.md"})
        )
        assert "agent decision" in bundle.text
        assert "boilerplate" not in bundle.text

    @pytest.mark.parametrize("arm", ARMS)
    def test_pristine_copier_answers_are_excluded_symmetrically(
        self, tmp_path: Path, arm: str
    ) -> None:
        workspace = tmp_path / arm
        workspace.mkdir()
        (workspace / ".copier-answers.yml").write_text(
            "_commit: v1.2.3\nproject_name: demo\n", encoding="utf-8"
        )
        (workspace / "app.py").write_text("answer = 42\n", encoding="utf-8")
        settings = JudgeSettings(
            panel=(RoleSettings(provider="codex"),),
            exclude=(".copier-answers.yml",),
        )

        bundle = bundle_workspace(workspace, settings)

        assert ".copier-answers.yml" not in bundle.text
        assert "app.py" in bundle.text

    def test_bundle_excludes_are_applied_and_order_is_deterministic(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "b.py").write_text("b = 1\n", encoding="utf-8")
        (tmp_path / "src" / "a.py").write_text("a = 1\n", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("secret contract\n", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "adr.md").write_text("decision\n", encoding="utf-8")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
        settings = JudgeSettings(
            panel=(RoleSettings(provider="codex"),),
            exclude=("AGENTS.md", "docs/*"),
        )
        bundle = bundle_workspace(tmp_path, settings)
        assert "secret contract" not in bundle.text
        assert "decision" not in bundle.text
        assert "ref" not in bundle.text
        assert bundle.file_count == 2
        assert bundle.text.index("src/a.py") < bundle.text.index("src/b.py")

    def test_long_files_are_truncated(self, tmp_path: Path) -> None:
        (tmp_path / "big.py").write_text("x = 1\n" * 10_000, encoding="utf-8")
        settings = JudgeSettings(
            panel=(RoleSettings(provider="codex"),), max_file_chars=100
        )
        bundle = bundle_workspace(tmp_path, settings)
        assert bundle.truncated_files == ("big.py",)
        assert "truncated for length" in bundle.text

    def test_assignments_cover_both_orders_deterministically(self) -> None:
        first, second = assignments_for_seed((ARM_BARE, ARM_GUARDRAILS), seed=0)
        again_first, again_second = assignments_for_seed((ARM_BARE, ARM_GUARDRAILS), seed=0)
        assert (first, second) == (again_first, again_second)
        assert first["a"] == second["b"] and first["b"] == second["a"]
        assert {first["a"], first["b"]} == {ARM_BARE, ARM_GUARDRAILS}

    def test_parse_judgment_maps_labels_to_arms(self) -> None:
        assignment = {"a": ARM_GUARDRAILS, "b": ARM_BARE}
        judgment = parse_judgment(
            _outcome(structured=_judge_payload(preference="b")),
            judge="codex:default",
            order_index=1,
            assignment=assignment,
        )
        assert judgment.preference_arm == ARM_BARE
        assert judgment.scores[ARM_GUARDRAILS]["domain_and_invariants"] == 7
        assert judgment.scores[ARM_BARE]["domain_and_invariants"] == 5

    def test_parse_judgment_rejects_missing_structure(self) -> None:
        with pytest.raises(JudgingError, match="structured"):
            parse_judgment(
                _outcome(structured=None),
                judge="codex:default",
                order_index=0,
                assignment={"a": ARM_BARE, "b": ARM_GUARDRAILS},
            )

    def test_aggregate_reports_preferences_and_position_flips(self) -> None:
        assignment_one = {"a": ARM_BARE, "b": ARM_GUARDRAILS}
        assignment_two = {"a": ARM_GUARDRAILS, "b": ARM_BARE}
        stable = [
            parse_judgment(
                _outcome(structured=_judge_payload(preference=label)),
                judge="judge-stable",
                order_index=index,
                assignment=assignment,
            )
            for index, (assignment, label) in enumerate(
                [(assignment_one, "b"), (assignment_two, "a")]
            )
        ]
        flipping = [
            parse_judgment(
                _outcome(structured=_judge_payload(preference="a")),
                judge="judge-flip",
                order_index=index,
                assignment=assignment,
            )
            for index, assignment in enumerate([assignment_one, assignment_two])
        ]
        aggregate = aggregate_judgments(stable + flipping, (ARM_BARE, ARM_GUARDRAILS))
        assert aggregate["preferences"][ARM_GUARDRAILS] == 3
        assert aggregate["preferences"][ARM_BARE] == 1
        assert aggregate["position_consistency"] == {
            "judge-stable": True,
            "judge-flip": False,
        }
        assert aggregate["primary_preferences"] == {
            ARM_BARE: 0,
            ARM_GUARDRAILS: 1,
            "tie": 0,
        }, "flipped judges must carry no weight in the primary endpoint"
        assert aggregate["paired_judge_count"] == 2
        assert aggregate["tool_calls_total"] == 20

    def test_unpaired_judgments_are_excluded_from_dimension_means(self) -> None:
        """A judge whose second order failed must not inject uncancelled bias."""
        paired = [
            parse_judgment(
                _outcome(structured=_judge_payload(preference="a")),
                judge="paired-judge",
                order_index=index,
                assignment=assignment,
            )
            for index, assignment in enumerate(
                [
                    {"a": ARM_BARE, "b": ARM_GUARDRAILS},
                    {"a": ARM_GUARDRAILS, "b": ARM_BARE},
                ]
            )
        ]
        lonely_payload = _judge_payload(preference="a")
        lonely_payload["candidate_a"] = {  # type: ignore[index]
            **{dimension: 0 for dimension in DIMENSIONS},
            "top_risk": "half judge",
        }
        lonely = parse_judgment(
            _outcome(structured=lonely_payload),
            judge="half-judge",
            order_index=0,
            assignment={"a": ARM_BARE, "b": ARM_GUARDRAILS},
        )
        aggregate = aggregate_judgments([*paired, lonely], (ARM_BARE, ARM_GUARDRAILS))
        assert aggregate["dimension_means"][ARM_BARE]["spec_fidelity"] == 7.0
        assert aggregate["position_consistency"] == {"paired-judge": False}


class _FakeRunner:
    """Builder writes a marker file; judges return a canned structured verdict."""

    def __init__(self, role: RoleSettings, journal: list[tuple[str, str, str | None]]) -> None:
        self._role = role
        self._journal = journal

    def run(
        self,
        prompt: str,
        *,
        working_directory: str | None = None,
        timeout_seconds: float,
        output_schema: dict[str, object] | None = None,
    ) -> AgentOutcome:
        del timeout_seconds
        if output_schema is None:
            self._journal.append(("build", prompt, working_directory))
            assert working_directory is not None
            (Path(working_directory) / "built_by_fake.py").write_text(
                "answer = 42\n", encoding="utf-8"
            )
            return _outcome(text="built")
        self._journal.append(("judge", prompt, working_directory))
        return _outcome(structured=_judge_payload(preference="a"))


def _pipeline_config(tmp_path: Path) -> BenchmarkConfig:
    source = tmp_path / "config.toml"
    source.write_text("# synthetic config (constructed in code)\n", encoding="utf-8")
    return BenchmarkConfig(
        source_path=source,
        run=RunSettings(
            output_root=tmp_path / "runs",
            label="fake",
            seed=7,
            keep_workspaces=True,
            run_native_gate=False,
        ),
        project=ProjectSettings(name="demo", package="demo"),
        template=TemplateSettings(answers={}),
        builder=BuilderSettings(provider="claude", timeout_seconds=10.0),
        judge=JudgeSettings(
            panel=(
                RoleSettings(provider="codex"),
                RoleSettings(provider="opencode", model="minimax/MiniMax-M3"),
            ),
            exclude=("AGENTS.md", "docs/*", "scripts/*", "*.lock"),
        ),
        probes=(
            ProbeSpec(name="marker-exists", argv=(sys.executable, "{ws}/built_by_fake.py")),
        ),
        tools=ToolPins(ruff="1", basedpyright="1", radon="1", coverage="1"),
        spec_text="specification body " * 20,
        charter_text="charter body",
    )


class TestOrchestration:
    def test_build_and_maintenance_use_fresh_agents_and_phase_tagged_results(
        self, tmp_path: Path
    ) -> None:
        journal: list[tuple[str, str, str | None]] = []
        builder_instances: list[_FakeRunner] = []
        cfg = replace(
            _pipeline_config(tmp_path),
            maintenance=ScenarioPhase(
                spec_text="maintenance change request " * 20,
                probes=(
                    ProbeSpec(
                        name="regression-marker-exists",
                        argv=(sys.executable, "{ws}/built_by_fake.py"),
                    ),
                ),
            ),
        )

        def factory(role: RoleSettings) -> _FakeRunner:
            runner = _FakeRunner(role, journal)
            if role.provider == cfg.builder.provider:
                builder_instances.append(runner)
            return runner

        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=factory,
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )

        assert list(run.results["phases"]) == ["build", "maintenance"]
        for phase in ("build", "maintenance"):
            assert set(run.results["phases"][phase]["arms"]) == set(ARMS)
            assert run.results["phases"][phase]["phase"] == phase
        assert len(builder_instances) == 4
        assert len({id(runner) for runner in builder_instances}) == 4
        agent_prompts = [entry[1] for entry in journal if entry[0] == "build"]
        assert agent_prompts[:2] == [
            compose_build_prompt(cfg.charter_text, cfg.spec_text)
        ] * 2
        assert agent_prompts[2:] == [cfg.maintenance.spec_text.strip() + "\n"] * 2

        rows = [
            json.loads(line)
            for line in (cfg.run.output_root / "registry.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert [(row["phase"], row["arm"]) for row in rows] == [
            ("build", ARM_BARE),
            ("build", ARM_GUARDRAILS),
            ("maintenance", ARM_BARE),
            ("maintenance", ARM_GUARDRAILS),
        ]
        report = (run.run_dir / "report.md").read_text(encoding="utf-8")
        assert "## Build phase" in report
        assert "## Maintenance phase" in report
        assert "| Maintenance effort |" in report
        assert "| Change wall time (s) |" in report

    def test_maintenance_fairness_uses_identical_prompt_bytes_and_probe_lists(
        self, tmp_path: Path
    ) -> None:
        journal: list[tuple[str, str, str | None]] = []
        received: list[ev.Event] = []
        cfg = replace(
            _pipeline_config(tmp_path),
            maintenance=ScenarioPhase(
                spec_text="make this exact maintenance change " * 20,
                probes=(
                    ProbeSpec(
                        name="new-behavior",
                        argv=(sys.executable, "{ws}/built_by_fake.py"),
                    ),
                    ProbeSpec(
                        name="build-regression",
                        argv=(sys.executable, "{ws}/built_by_fake.py"),
                    ),
                ),
            ),
        )

        run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
            events=received.append,
        )

        maintenance_prompts = [
            entry[1]
            for entry in journal
            if entry[0] == "build" and entry[1] != compose_build_prompt(cfg.charter_text, cfg.spec_text)
        ]
        assert len(maintenance_prompts) == 2
        assert maintenance_prompts[0].encode() == maintenance_prompts[1].encode()
        for arm in ARMS:
            assert [
                event.payload["name"]
                for event in received
                if event.kind == ev.PROBE_RESULT
                and event.phase == "maintenance"
                and event.arm == arm
            ] == ["new-behavior", "build-regression"]

    def test_shipped_smoke_config_runs_with_fake_agents_without_prompting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from benchmarks.e2e import workspaces

        cfg = load_config(
            REPO_ROOT / "benchmarks" / "config" / "smoke.toml",
            repo_root=REPO_ROOT,
        )
        cfg = replace(
            cfg,
            run=replace(
                cfg.run,
                output_root=tmp_path / "runs",
                keep_workspaces=True,
                run_native_gate=False,
            ),
            probes=(
                ProbeSpec(
                    name="fake-marker",
                    argv=(sys.executable, "{ws}/built_by_fake.py"),
                ),
            ),
        )
        real_run_copy = workspaces.run_copy
        copier_calls = 0

        def run_copy_without_prompts(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            nonlocal copier_calls
            copier_calls += 1
            assert kwargs.get("defaults") is True
            return real_run_copy(*args, **kwargs)

        class PromptTrap:
            def isatty(self) -> bool:
                return True

            def read(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
                raise AssertionError("Copier attempted to read from stdin")

            def readline(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
                raise AssertionError("Copier attempted to prompt on stdin")

        monkeypatch.setattr(workspaces, "run_copy", run_copy_without_prompts)
        monkeypatch.setattr(sys, "stdin", PromptTrap())
        journal: list[tuple[str, str, str | None]] = []

        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )

        assert copier_calls == 1
        assert all(
            arm["probes"]["pass_rate"] == 1.0
            for arm in run.results["arms"].values()
        )

    @pytest.mark.parametrize(
        ("variant", "answers"),
        (
            ("no-precommit", {"precommit": False}),
            ("no-agents-md", {"agents_contract": "none"}),
            ("checks-via-commit", {"agents_contract": "hooks-first"}),
        ),
    )
    def test_bare_workspace_ignores_every_variant_configuration(
        self, tmp_path: Path, variant: str, answers: dict[str, object]
    ) -> None:
        cfg = _pipeline_config(tmp_path)
        first = replace(
            cfg,
            template=TemplateSettings(
                vcs_ref="HEAD", variant="baseline", answers={}
            ),
        )
        second = replace(
            cfg,
            template=TemplateSettings(
                vcs_ref="ref-that-does-not-exist",
                variant=variant,
                answers={
                    "project_name": "different",
                    "package": "different",
                    **answers,
                },
            ),
        )

        first_workspace = prepare_workspace(
            ARM_BARE, first, tmp_path / "first", repo_root=REPO_ROOT
        )
        second_workspace = prepare_workspace(
            ARM_BARE, second, tmp_path / "second", repo_root=REPO_ROOT
        )

        tree_ids = [
            subprocess.run(
                ("git", "rev-parse", "HEAD^{tree}"),
                cwd=workspace.path,
                env=git_environment(),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            for workspace in (first_workspace, second_workspace)
        ]
        assert tree_ids[0] == tree_ids[1]
        assert first_workspace.template_identity is None
        assert second_workspace.template_identity is None

    def test_copier_identity_and_answers_are_recorded(self, tmp_path: Path) -> None:
        journal: list[tuple[str, str, str | None]] = []
        cfg = _pipeline_config(tmp_path)
        cfg = replace(
            cfg,
            template=TemplateSettings(
                vcs_ref="HEAD",
                variant="baseline",
                answers={"package": "configured_demo"},
            ),
        )
        expected_version = subprocess.run(
            ("git", "describe", "--tags", "--always", "--dirty"),
            cwd=REPO_ROOT,
            env=git_environment(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )

        expected_identity = {
            "version": expected_version,
            "vcs_ref": "HEAD",
            "variant": "baseline",
            "answers": {
                "agents_contract": "full",
                "project_name": "demo",
                "package": "configured_demo",
                "precommit": True,
                "workspace_member": False,
            },
        }
        manifest = json.loads(
            (run.run_dir / "manifest.json").read_text(encoding="utf-8")
        )
        serialized_results = json.loads(
            (run.run_dir / "results.json").read_text(encoding="utf-8")
        )
        assert manifest["template"] == expected_identity
        assert run.results["meta"]["template"] == expected_identity
        assert serialized_results["meta"]["template"] == expected_identity
        report = (run.run_dir / "report.md").read_text(encoding="utf-8")
        assert expected_version in report
        assert "project_name=demo" in report
        assert "package=configured_demo" in report
        workspace = run.run_dir / "arms" / ARM_GUARDRAILS / "workspace"
        assert (workspace / "src" / "configured_demo").is_dir()

    def test_fake_agent_run_applies_and_records_variant(self, tmp_path: Path) -> None:
        cfg = replace(
            _pipeline_config(tmp_path),
            template=TemplateSettings(
                vcs_ref="HEAD",
                variant="checks-via-commit",
                answers={"agents_contract": "hooks-first"},
            ),
        )

        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, []),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )

        expected_answers = {
            "agents_contract": "hooks-first",
            "package": "demo",
            "precommit": True,
            "project_name": "demo",
            "workspace_member": False,
        }
        workspace = run.run_dir / "arms" / ARM_GUARDRAILS / "workspace"
        recorded_answers = safe_load(
            (workspace / ".copier-answers.yml").read_text(encoding="utf-8")
        )
        assert {
            key: value
            for key, value in recorded_answers.items()
            if not key.startswith("_")
        } == expected_answers
        assert "Publication is complete when the commit and pre-push hooks succeed" in (
            workspace / "AGENTS.md"
        ).read_text(encoding="utf-8")

        manifest = json.loads(
            (run.run_dir / "manifest.json").read_text(encoding="utf-8")
        )
        serialized_results = json.loads(
            (run.run_dir / "results.json").read_text(encoding="utf-8")
        )
        assert manifest["template"]["variant"] == "checks-via-commit"
        assert manifest["template"]["answers"] == expected_answers
        assert serialized_results["meta"]["template"] == manifest["template"]

        registry_rows = [
            json.loads(line)
            for line in (cfg.run.output_root / "registry.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert [row["variant"] for row in registry_rows] == [
            "checks-via-commit",
            "checks-via-commit",
        ]
        assert all(row["template"] == manifest["template"] for row in registry_rows)

    def test_dirty_template_identity_is_flagged_in_fake_agent_pipeline(
        self, tmp_path: Path
    ) -> None:
        template_repo = tmp_path / "template-repo"
        template_repo.mkdir()
        shutil.copy(REPO_ROOT / "copier.yml", template_repo / "copier.yml")
        shutil.copytree(REPO_ROOT / "template", template_repo / "template")
        subprocess.run(
            ("git", "init", "--quiet", "--initial-branch=main"),
            cwd=template_repo,
            env=git_environment(),
            check=True,
        )
        subprocess.run(
            ("git", "add", "--all"),
            cwd=template_repo,
            env=git_environment(),
            check=True,
        )
        subprocess.run(
            (
                "git",
                "-c",
                "user.name=tests",
                "-c",
                "user.email=tests@localhost",
                "commit",
                "--quiet",
                "--message=tagged template",
            ),
            cwd=template_repo,
            env=git_environment(),
            check=True,
        )
        subprocess.run(
            ("git", "tag", "v0.1.0"),
            cwd=template_repo,
            env=git_environment(),
            check=True,
        )
        readme = template_repo / "template" / "README.md.jinja"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir()
        cfg = _pipeline_config(pipeline_dir)
        journal: list[tuple[str, str, str | None]] = []

        run = run_benchmark(
            cfg,
            repo_root=template_repo,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )

        assert run.results["meta"]["template"]["version"] == "v0.1.0-dirty"
        serialized = json.loads(
            (run.run_dir / "results.json").read_text(encoding="utf-8")
        )
        assert serialized["meta"]["template"]["version"] == "v0.1.0-dirty"

    def test_full_pipeline_with_fake_agents(self, tmp_path: Path) -> None:
        journal: list[tuple[str, str, str | None]] = []
        cfg = _pipeline_config(tmp_path)
        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {"loc": loc_summary(workspace)},
            log=lambda message: None,
        )

        build_prompts = [entry[1] for entry in journal if entry[0] == "build"]
        assert len(build_prompts) == 2
        assert build_prompts[0] == build_prompts[1], "arms must receive the identical prompt"
        assert build_prompts[0] == compose_build_prompt(cfg.charter_text, cfg.spec_text)

        judge_prompts = [entry[1] for entry in journal if entry[0] == "judge"]
        assert len(judge_prompts) == len(cfg.judge.panel) * 2
        assert all("--- file: AGENTS.md ---" not in prompt for prompt in judge_prompts), (
            "excluded files must not be bundled for the judge"
        )
        judge_cwds = {entry[2] for entry in journal if entry[0] == "judge"}
        assert len(judge_cwds) == 1
        judge_cwd = judge_cwds.pop()
        assert judge_cwd is not None, "judges must not inherit the harness CWD"
        assert "guardrails" not in judge_cwd and "workspace" not in judge_cwd, (
            "the judge working directory path must not reveal provenance"
        )

        arms = run.results["arms"]
        assert isinstance(arms, dict) and set(arms) == set(ARMS)
        for arm in ARMS:
            assert arms[arm]["probes"]["pass_rate"] == 1.0
            assert arms[arm]["build"]["cost_provenance"] == "computed"
            assert arms[arm]["build"]["reasoning_tokens"] == 25
        aggregate = run.results["judging"]["aggregate"]
        assert aggregate["judgment_count"] == 4
        preference_total = sum(aggregate["preferences"].values())
        assert preference_total == 4

        report = (run.run_dir / "report.md").read_text(encoding="utf-8")
        for artifact in ("manifest.json", "results.json", "build_prompt.md", "config.toml"):
            assert (run.run_dir / artifact).is_file()
        assert "Functional probe" in report
        assert "Limitations" in report
        assert "Maintenance used fresh agent sessions" not in report
        guardrails_src = run.run_dir / "arms" / ARM_GUARDRAILS / "workspace" / "src" / "demo"
        assert guardrails_src.is_dir(), "guardrails arm must start from the instantiated template"

    def test_completed_runs_append_well_formed_registry_rows(
        self, tmp_path: Path
    ) -> None:
        cfg = _pipeline_config(tmp_path)
        metric_summary = {
            "ruff": {"per_kloc": 1.5},
            "basedpyright": {"errors_per_kloc": 2.5},
            "coverage": {"percent": 87.5},
        }

        first = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, []),
            metrics_collector=lambda workspace, out_dir: metric_summary,
            log=lambda message: None,
        )
        second = run_benchmark(
            replace(cfg, run=replace(cfg.run, label="fake-second")),
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, []),
            metrics_collector=lambda workspace, out_dir: metric_summary,
            log=lambda message: None,
        )

        registry = cfg.run.output_root / "registry.jsonl"
        rows = [
            json.loads(line)
            for line in registry.read_text(encoding="utf-8").splitlines()
        ]
        assert len(rows) == 4
        assert [row["run_id"] for row in rows[:2]] == [
            first.results["meta"]["run_id"],
            first.results["meta"]["run_id"],
        ]
        assert [row["run_id"] for row in rows[2:]] == [
            second.results["meta"]["run_id"],
            second.results["meta"]["run_id"],
        ]
        assert [row["arm"] for row in rows] == [*ARMS, *ARMS]

        first_manifest = json.loads(
            (first.run_dir / "manifest.json").read_text(encoding="utf-8")
        )
        for row in rows[:2]:
            assert row == {
                "schema_version": 1,
                "run_id": first.results["meta"]["run_id"],
                "started_utc": first.results["meta"]["started_utc"],
                "run_label": "fake",
                "arm": row["arm"],
                "template": first_manifest["template"],
                "variant": "baseline",
                "app": "demo",
                "phase": "build",
                "provider": "claude",
                "model": "fake-model",
                "effort": None,
                "seed": 7,
                "pack_revision": first.results["meta"]["pack_revision"],
                "headless_llm_revision": first.results["meta"]["headless_llm_revision"],
                "probe_pass_rate": 1.0,
                "judge_primary_endpoint": first.results["judging"]["aggregate"][
                    "primary_preferences"
                ],
                "judge_dimension_means": first.results["judging"]["aggregate"][
                    "dimension_means"
                ][row["arm"]],
                "analyzer_densities": {
                    "ruff_violations_per_kloc": 1.5,
                    "basedpyright_errors_per_kloc": 2.5,
                },
                "coverage_percent": 87.5,
                "wall_time_seconds": 1.2,
                "cost_usd": 0.01,
                "input_tokens": 100,
                "cached_input_tokens": 0,
                "output_tokens": 50,
                "reasoning_tokens": 25,
                "tool_calls": 5,
                "turns": 3,
            }

    def test_structured_events_cover_both_arms_and_judging(self, tmp_path: Path) -> None:
        """The TUI contract: stages, probes, builds, and verdicts all emit events."""
        from benchmarks.e2e import events as ev

        journal: list[tuple[str, str, str | None]] = []
        received: list[ev.Event] = []
        cfg = _pipeline_config(tmp_path)
        run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {"loc": loc_summary(workspace)},
            log=lambda message: None,
            events=received.append,
        )
        kinds = [event.kind for event in received]
        assert kinds[0] == ev.RUN_STARTED
        assert kinds[-1] == ev.RUN_FINISHED
        for arm in ARMS:
            arm_stages = [
                event.payload["stage"]
                for event in received
                if event.kind == ev.ARM_STAGE and event.arm == arm
            ]
            assert arm_stages == list(ev.ARM_STAGES)
            assert any(event.kind == ev.BUILD_FINISHED and event.arm == arm for event in received)
            assert any(event.kind == ev.PROBE_RESULT and event.arm == arm for event in received)
            assert any(event.kind == ev.METRICS_READY and event.arm == arm for event in received)
        assert sum(1 for event in received if event.kind == ev.JUDGMENT) == 4

    def test_arms_run_concurrently_by_default(self, tmp_path: Path) -> None:
        """Both builds must be in flight at the same time (parallel_arms)."""
        import threading

        barrier = threading.Barrier(2, timeout=10.0)
        journal: list[tuple[str, str, str | None]] = []

        class _BarrierRunner(_FakeRunner):
            def run(self, prompt, **kwargs):  # noqa: ANN003, ANN001, ANN202
                if kwargs.get("output_schema") is None:
                    barrier.wait()
                return super().run(prompt, **kwargs)

        cfg = _pipeline_config(tmp_path)
        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _BarrierRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )
        assert all(
            arm_results["build"]["error"] is None
            for arm_results in run.results["arms"].values()
        ), "a broken barrier means the arms ran sequentially"

    def test_sequential_mode_still_works(self, tmp_path: Path) -> None:
        journal: list[tuple[str, str, str | None]] = []
        cfg = _pipeline_config(tmp_path)
        cfg = replace(cfg, run=replace(cfg.run, parallel_arms=False))
        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )
        assert run.results["judging"]["aggregate"]["judgment_count"] == 4

    def test_workspaces_are_removed_when_not_kept(self, tmp_path: Path) -> None:
        journal: list[tuple[str, str, str | None]] = []
        cfg = _pipeline_config(tmp_path)
        cfg = replace(cfg, run=replace(cfg.run, keep_workspaces=False))
        run = run_benchmark(
            cfg,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, journal),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )
        assert not (run.run_dir / "arms").exists()
        assert (run.run_dir / "report.md").is_file()


class TestReporting:
    def test_render_report_survives_partial_results(self) -> None:
        report = render_report({"meta": {"run_id": "x"}, "arms": {}, "judging": {}})
        assert "# Template value benchmark" in report
        assert "Limitations" in report

    def test_render_report_shows_probe_rows(self) -> None:
        results = {
            "meta": {"run_id": "x", "builder": "claude:m", "judges": ["codex:default"]},
            "arms": {
                ARM_BARE: {
                    "probes": {
                        "results": [{"name": "adds", "passed": False}],
                        "pass_rate": 0.0,
                    }
                },
                ARM_GUARDRAILS: {
                    "probes": {
                        "results": [{"name": "adds", "passed": True}],
                        "pass_rate": 1.0,
                    }
                },
            },
            "judging": {},
        }
        report = render_report(results)
        assert "| adds | FAIL | pass |" in report

    def test_render_report_labels_cost_provenance(self) -> None:
        results = {
            "meta": {"run_id": "x"},
            "arms": {
                ARM_BARE: {
                    "build": {
                        "cost_usd": 0.01,
                        "cost_provenance": "computed",
                        "reasoning_tokens": 25,
                    }
                },
                ARM_GUARDRAILS: {
                    "build": {"cost_usd": 0.02, "cost_provenance": "reported"}
                },
            },
            "judging": {},
        }

        report = render_report(results)

        assert "| Cost (USD, cache included) | 0.01 | 0.02 |" in report
        assert "| Cost provenance | computed | reported |" in report
        assert "| Reasoning tokens | 25 | — |" in report
        assert "Token counts are comparable only within a provider" in report
