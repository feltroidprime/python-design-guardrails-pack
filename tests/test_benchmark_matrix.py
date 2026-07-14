"""Deterministic campaign tests: real pipeline, fake agents, no network."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import pytest
from yaml import safe_load

from benchmarks.e2e.agents import AgentOutcome
from benchmarks.e2e.config import ARMS, ConfigError, RoleSettings
from benchmarks.e2e.judging import DIMENSIONS
from benchmarks.e2e.matrix import load_matrix_config, plan_matrix, run_matrix
from benchmarks.e2e.workspaces import git_environment


REPO_ROOT = Path(__file__).resolve().parents[1]


def _single_config(root: Path, name: str, marker: str) -> Path:
    spec = root / f"{name}-spec.md"
    spec.write_text(
        f"{marker}\n" + "Build this deterministic demo application. " * 12,
        encoding="utf-8",
    )
    charter = root / "charter.md"
    charter.write_text(
        "Implement the supplied specification exactly.", encoding="utf-8"
    )
    path = root / f"{name}.toml"
    path.write_text(
        f"""
[run]
output_root = {json.dumps(str(root / "unused-single-runs"))}
label = {json.dumps(name)}
seed = 0
keep_workspaces = true
run_native_gate = false
parallel_arms = true

[project]
name = {json.dumps(name)}
package = {json.dumps(name.replace("-", "_"))}

[template]
vcs_ref = "HEAD"
variant = "baseline"

[builder]
provider = "claude"
model = "base-model"
timeout_seconds = 10
allowed_tools = ["Read", "Write"]

[judge]
timeout_seconds = 10
exclude = [".copier-answers.yml"]

[[judge.panel]]
provider = "opencode"
model = "minimax/MiniMax-M3"

[prompt]
spec_file = {json.dumps(spec.name)}
charter_file = {json.dumps(charter.name)}

[[probes]]
name = "fake-built"
argv = ["python3", "{{ws}}/built_by_fake.py"]

[tools]
ruff = "1"
basedpyright = "1"
radon = "1"
coverage = "1"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _add_maintenance(root: Path, app: Path, marker: str) -> Path:
    spec = root / f"{app.stem}-maintenance.md"
    spec.write_text(
        f"{marker}\n" + "Change this deterministic demo application. " * 12,
        encoding="utf-8",
    )
    app.write_text(
        app.read_text(encoding="utf-8")
        + f"""

[scenario.maintenance]
spec_file = {json.dumps(spec.name)}

[[scenario.maintenance.probes]]
name = "fake-maintained"
argv = ["python3", "{{ws}}/built_by_fake.py"]
""",
        encoding="utf-8",
    )
    return app


def _matrix_config(
    root: Path,
    apps: list[Path],
    *,
    builders: str | None = None,
    variants: str = '["baseline"]',
    seeds: str = "[11, 22]",
    repetitions: int = 1,
    judge: str | None = None,
    concurrency: str | None = None,
) -> Path:
    builders = (
        builders
        or """
[[builders]]
provider = "claude"
model = "claude-test"

[[builders]]
provider = "codex"
model = "gpt-test"
effort = "high"
binary = "codex-test-bin"
"""
    )
    judge = (
        judge
        or """
[judge]

[[judge.panel]]
provider = "opencode"
model = "minimax/MiniMax-M3"
family = "minimax"
"""
    )
    concurrency = (
        concurrency
        or """
[concurrency]
claude = 1
codex = 2
opencode = 1
"""
    )
    path = root / "matrix.toml"
    path.write_text(
        f"""
[run]
output_root = {json.dumps(str(root / "campaign-runs"))}
label = "test-campaign"
headless_llm_path = {json.dumps(str(root / "unused-headless"))}

[matrix]
apps = {json.dumps([app.name for app in apps])}
seeds = {seeds}
variants = {variants}
repetitions = {repetitions}

[template]
vcs_ref = "HEAD"

{builders}
{judge}
{concurrency}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _judge_payload() -> dict[str, object]:
    scores = {dimension: 6 for dimension in DIMENSIONS}
    scores["top_risk"] = "none"
    return {
        "preference": "a",
        "preference_strength": "slight",
        "candidate_a": dict(scores),
        "candidate_b": dict(scores),
        "summary": "equivalent fake implementations",
    }


class _Concurrency:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active: defaultdict[str, int] = defaultdict(int)
        self.peaks: defaultdict[str, int] = defaultdict(int)
        self.build_prompts: list[str] = []
        self.build_calls = 0

    def enter(self, provider: str, prompt: str, *, build: bool) -> None:
        with self.lock:
            self.active[provider] += 1
            self.peaks[provider] = max(self.peaks[provider], self.active[provider])
            if build:
                self.build_prompts.append(prompt)
                self.build_calls += 1

    def leave(self, provider: str) -> None:
        with self.lock:
            self.active[provider] -= 1


class _FakeRunner:
    def __init__(self, role: RoleSettings, concurrency: _Concurrency) -> None:
        self.role = role
        self.concurrency = concurrency

    def run(
        self,
        prompt: str,
        *,
        working_directory: str | None = None,
        timeout_seconds: float,
        output_schema: dict[str, object] | None = None,
    ) -> AgentOutcome:
        del timeout_seconds
        build = output_schema is None
        self.concurrency.enter(self.role.provider, prompt, build=build)
        try:
            time.sleep(0.01)
            if build:
                assert working_directory is not None
                (Path(working_directory) / "built_by_fake.py").write_text(
                    "answer = 42\n", encoding="utf-8"
                )
            return AgentOutcome(
                text="built" if build else "judged",
                structured=None if build else _judge_payload(),
                model=self.role.model,
                duration_ms=10,
                turns=1,
                tool_calls=1,
                input_tokens=10,
                output_tokens=5,
                reasoning_tokens=1,
                cached_input_tokens=0,
                cost_usd=0.001,
                cost_provenance="computed",
            )
        finally:
            self.concurrency.leave(self.role.provider)


def _apps(root: Path) -> list[Path]:
    return [
        _single_config(root, "alpha-app", "ALPHA-SPEC-MARKER"),
        _single_config(root, "beta-app", "BETA-SPEC-MARKER"),
    ]


def _copy_variant_answers(pack: Path) -> None:
    destination = pack / "benchmarks" / "config" / "variants"
    destination.mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / "benchmarks" / "config" / "variants" / "answers.toml",
        destination / "answers.toml",
    )


def test_small_matrix_completes_with_full_identity_and_fair_prompts(
    tmp_path: Path,
) -> None:
    matrix = load_matrix_config(
        _matrix_config(tmp_path, _apps(tmp_path)), repo_root=REPO_ROOT
    )
    concurrency = _Concurrency()

    result = run_matrix(
        matrix,
        repo_root=REPO_ROOT,
        runner_factory=lambda role: _FakeRunner(role, concurrency),
        metrics_collector=lambda workspace, out_dir: {},
        log=lambda message: None,
    )

    assert len(result.completed) == 8
    assert result.skipped == ()
    registry_rows = [
        json.loads(line)
        for line in (matrix.run.output_root / "registry.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(registry_rows) == 16
    assert {row["arm"] for row in registry_rows} == set(ARMS)
    assert {row["matrix"]["repetition"] for row in registry_rows} == {1}
    assert {row["matrix"]["app"] for row in registry_rows} == {
        "alpha-app",
        "beta-app",
    }
    assert {row["matrix"]["seed"] for row in registry_rows} == {11, 22}
    assert {row["matrix"]["variant"] for row in registry_rows} == {"baseline"}
    assert {row["matrix"]["builder"]["provider"] for row in registry_rows} == {
        "claude",
        "codex",
    }
    assert all(row["template"]["version"] for row in registry_rows)
    assert all(row["template"]["vcs_ref"] == "HEAD" for row in registry_rows)

    alpha_prompts = {
        prompt for prompt in concurrency.build_prompts if "ALPHA-SPEC-MARKER" in prompt
    }
    beta_prompts = {
        prompt for prompt in concurrency.build_prompts if "BETA-SPEC-MARKER" in prompt
    }
    assert len(alpha_prompts) == len(beta_prompts) == 1

    manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in matrix.run.output_root.glob("*/manifest.json")
    ]
    assert len(manifests) == 8
    codex_manifests = [
        item for item in manifests if item["builder_settings"]["provider"] == "codex"
    ]
    claude_manifests = [
        item for item in manifests if item["builder_settings"]["provider"] == "claude"
    ]
    assert all(
        item["builder_settings"]["allowed_tools"] is None for item in codex_manifests
    )
    assert all(
        item["builder_settings"]["binary"] == "codex-test-bin"
        for item in codex_manifests
    )
    assert all(
        item["builder_settings"]["allowed_tools"] == ["Read", "Write"]
        for item in claude_manifests
    )
    assert all(item["matrix"]["cell_id"] for item in manifests)
    assert all(
        item["matrix"]["template_identity"]["version"]
        == item["template"]["version"]
        for item in manifests
    )

    assert dict(concurrency.peaks) == {"claude": 1, "codex": 2, "opencode": 1}


def test_dry_run_lists_every_cell_without_creating_output(tmp_path: Path) -> None:
    matrix = load_matrix_config(
        _matrix_config(tmp_path, _apps(tmp_path)), repo_root=REPO_ROOT
    )
    messages: list[str] = []
    concurrency = _Concurrency()

    result = run_matrix(
        matrix,
        repo_root=REPO_ROOT,
        runner_factory=lambda role: _FakeRunner(role, concurrency),
        dry_run=True,
        log=messages.append,
    )

    assert len(result.planned) == 8
    assert result.completed == result.skipped == ()
    assert messages[0] == "planned matrix cells: 8"
    assert any(
        "alpha-app" in message and "claude:claude-test" in message
        for message in messages
    )
    assert not matrix.run.output_root.exists()
    assert concurrency.build_calls == 0


def test_repetitions_expand_to_distinct_resumable_cells(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "repeat-app", "REPEAT-SPEC-MARKER")
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix = load_matrix_config(
        _matrix_config(
            tmp_path,
            [app],
            builders=builders,
            seeds="[11]",
            repetitions=2,
        ),
        repo_root=REPO_ROOT,
    )

    cells = plan_matrix(matrix)

    assert [cell.dimensions["repetition"] for cell in cells] == [1, 2]
    assert len({cell.cell_id for cell in cells}) == 2


def test_maintenance_request_is_part_of_cell_identity(tmp_path: Path) -> None:
    app = _add_maintenance(
        tmp_path,
        _single_config(tmp_path, "maintenance-app", "BUILD-SPEC-MARKER"),
        "FIRST-MAINTENANCE-MARKER",
    )
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix_path = _matrix_config(tmp_path, [app], builders=builders, seeds="[11]")
    first = plan_matrix(load_matrix_config(matrix_path, repo_root=REPO_ROOT))[0]
    maintenance_spec = tmp_path / "maintenance-app-maintenance.md"
    maintenance_spec.write_text(
        "SECOND-MAINTENANCE-MARKER\n"
        + "Change this deterministic demo application differently. " * 12,
        encoding="utf-8",
    )
    second = plan_matrix(load_matrix_config(matrix_path, repo_root=REPO_ROOT))[0]

    assert second.cell_id != first.cell_id


def test_dirty_working_tree_content_is_part_of_the_resume_identity(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "copier.yml").write_text("_subdirectory: template\n", encoding="utf-8")
    (pack / "template").mkdir()
    _copy_variant_answers(pack)
    marker = pack / "template" / "marker.txt"
    marker.write_text("committed\n", encoding="utf-8")
    subprocess.run(
        ("git", "init", "--quiet", "--initial-branch=main"),
        cwd=pack,
        env=git_environment(),
        check=True,
    )
    subprocess.run(
        ("git", "add", "--all"), cwd=pack, env=git_environment(), check=True
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
            "--message=initial",
        ),
        cwd=pack,
        env=git_environment(),
        check=True,
    )
    app = _single_config(tmp_path, "identity-app", "IDENTITY-SPEC-MARKER")
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix_path = _matrix_config(
        tmp_path, [app], builders=builders, seeds="[11]"
    )
    marker.write_text("dirty one\n", encoding="utf-8")
    first = plan_matrix(load_matrix_config(matrix_path, repo_root=pack))[0]
    marker.write_text("dirty two\n", encoding="utf-8")
    second = plan_matrix(load_matrix_config(matrix_path, repo_root=pack))[0]

    first_identity = first.dimensions["template_identity"]
    second_identity = second.dimensions["template_identity"]
    assert isinstance(first_identity, dict) and isinstance(second_identity, dict)
    assert str(first_identity["version"]).endswith("-dirty")
    assert second_identity["version"] == first_identity["version"]
    assert second.cell_id != first.cell_id


def test_template_symlinks_are_rejected_before_campaign_execution(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "copier.yml").write_text("_subdirectory: template\n", encoding="utf-8")
    (pack / "template").mkdir()
    external = tmp_path / "outside-secret.txt"
    external.write_text("must not enter a provider workspace\n", encoding="utf-8")
    (pack / "template" / "linked-secret.txt").symlink_to(external)
    _copy_variant_answers(pack)
    subprocess.run(
        ("git", "init", "--quiet", "--initial-branch=main"),
        cwd=pack,
        env=git_environment(),
        check=True,
    )
    subprocess.run(
        ("git", "add", "--all"), cwd=pack, env=git_environment(), check=True
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
            "--message=initial",
        ),
        cwd=pack,
        env=git_environment(),
        check=True,
    )
    app = _single_config(tmp_path, "symlink-app", "SYMLINK-SPEC-MARKER")

    with pytest.raises(ConfigError, match="unsupported symlink.*linked-secret"):
        load_matrix_config(
            _matrix_config(tmp_path, [app], seeds="[11]"), repo_root=pack
        )


def test_dirty_campaign_uses_one_immutable_template_snapshot(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    shutil.copy(REPO_ROOT / "copier.yml", pack / "copier.yml")
    shutil.copytree(REPO_ROOT / "template", pack / "template")
    _copy_variant_answers(pack)
    subprocess.run(
        ("git", "init", "--quiet", "--initial-branch=main"),
        cwd=pack,
        env=git_environment(),
        check=True,
    )
    subprocess.run(("git", "add", "--all"), cwd=pack, env=git_environment(), check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            "--message=initial",
        ),
        cwd=pack,
        env=git_environment(),
        check=True,
    )
    readme = pack / "template" / "README.md.jinja"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\nPINNED-CAMPAIGN-MARKER\n",
        encoding="utf-8",
    )
    app = _single_config(tmp_path, "snapshot-app", "SNAPSHOT-SPEC-MARKER")
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix = load_matrix_config(
        _matrix_config(
            tmp_path,
            [app],
            builders=builders,
            seeds="[11, 22]",
            concurrency="""
[concurrency]
claude = 1
codex = 1
opencode = 1
""",
        ),
        repo_root=pack,
    )
    concurrency = _Concurrency()
    mutation_lock = threading.Lock()
    mutated = False

    class MutatingRunner(_FakeRunner):
        def run(self, prompt: str, **kwargs: object) -> AgentOutcome:
            nonlocal mutated
            if kwargs.get("output_schema") is None:
                with mutation_lock:
                    if not mutated:
                        readme.write_text(
                            "MUTATED-AFTER-FIRST-CELL\n", encoding="utf-8"
                        )
                        mutated = True
            return super().run(prompt, **kwargs)

    result = run_matrix(
        matrix,
        repo_root=pack,
        runner_factory=lambda role: MutatingRunner(role, concurrency),
        metrics_collector=lambda workspace, out_dir: {},
        log=lambda message: None,
    )

    assert len(result.completed) == 2
    generated_readmes = list(
        matrix.run.output_root.glob("*/arms/guardrails/workspace/README.md")
    )
    assert len(generated_readmes) == 2
    assert all(
        "PINNED-CAMPAIGN-MARKER" in path.read_text(encoding="utf-8")
        for path in generated_readmes
    )


def test_snapshot_copier_commit_is_stable_across_invocations(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "stable-app", "STABLE-SPEC-MARKER")
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix = load_matrix_config(
        _matrix_config(tmp_path, [app], builders=builders, seeds="[11]"),
        repo_root=REPO_ROOT,
    )
    second = replace(
        matrix,
        run=replace(matrix.run, output_root=tmp_path / "second-campaign-runs"),
    )

    for campaign in (matrix, second):
        run_matrix(
            campaign,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: _FakeRunner(role, _Concurrency()),
            metrics_collector=lambda workspace, out_dir: {},
            log=lambda message: None,
        )

    answer_documents: list[str] = []
    for output_root in (matrix.run.output_root, second.run.output_root):
        answers_path = next(
            output_root.glob(
                "*/arms/guardrails/workspace/.copier-answers.yml"
            )
        )
        answer_documents.append(answers_path.read_text(encoding="utf-8"))

    assert answer_documents[0] == answer_documents[1]
    assert safe_load(answer_documents[0])["_commit"]


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_matrix_builder_does_not_inherit_app_model_or_effort(
    tmp_path: Path, provider: str
) -> None:
    app = _single_config(tmp_path, "defaults-app", "DEFAULTS-SPEC-MARKER")
    app.write_text(
        app.read_text(encoding="utf-8").replace(
            'model = "base-model"',
            'model = "base-model"\neffort = "base-effort"',
        ),
        encoding="utf-8",
    )
    builders = f"""
[[builders]]
provider = "{provider}"
"""
    matrix = load_matrix_config(
        _matrix_config(tmp_path, [app], builders=builders, seeds="[11]"),
        repo_root=REPO_ROOT,
    )

    builder = plan_matrix(matrix)[0].config.builder

    assert builder.model is None
    assert builder.effort is None
    assert builder.allowed_tools == (
        ("Read", "Write") if provider == "claude" else None
    )


def test_opencode_roles_require_a_model_for_family_validation(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "opencode-app", "OPENCODE-SPEC-MARKER")
    builders = """
[[builders]]
provider = "opencode"
"""

    with pytest.raises(ConfigError, match="opencode.*model.*family-disjointness rule"):
        load_matrix_config(
            _matrix_config(tmp_path, [app], builders=builders),
            repo_root=REPO_ROOT,
        )


def test_explicit_opencode_family_detects_gateway_overlap(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "gateway-app", "GATEWAY-SPEC-MARKER")
    builders = """
[[builders]]
provider = "opencode"
model = "openrouter/google/gemini-3.1-pro"
family = "google"
"""
    judge = """
[judge]

[[judge.panel]]
provider = "opencode"
model = "google/gemini-2.5-pro"
family = "google"
"""

    with pytest.raises(ConfigError, match="family-disjointness rule.*google"):
        load_matrix_config(
            _matrix_config(tmp_path, [app], builders=builders, judge=judge),
            repo_root=REPO_ROOT,
        )


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"seeds": "[11, 11]"}, "seeds.*unique"),
        ({"variants": '["baseline", "baseline"]'}, "variants.*unique"),
        (
            {
                "builders": """
[[builders]]
provider = "claude"
model = "claude-test"

[[builders]]
provider = "claude"
model = "claude-test"
"""
            },
            "builders.*unique",
        ),
    ],
)
def test_duplicate_matrix_dimensions_are_rejected(
    tmp_path: Path, overrides: dict[str, str], match: str
) -> None:
    app = _single_config(tmp_path, "duplicate-app", "DUPLICATE-SPEC-MARKER")

    with pytest.raises(ConfigError, match=match):
        load_matrix_config(
            _matrix_config(tmp_path, [app], **overrides), repo_root=REPO_ROOT
        )


def test_cli_dry_run_needs_no_provider_checkout_or_bootstrap(tmp_path: Path) -> None:
    matrix_path = _matrix_config(tmp_path, _apps(tmp_path))

    completed = subprocess.run(
        (
            sys.executable,
            str(REPO_ROOT / "benchmarks" / "matrix.py"),
            "--config",
            str(matrix_path),
            "--dry-run",
        ),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "planned matrix cells: 8" in completed.stdout
    assert "provider checkout" not in completed.stderr
    assert not (tmp_path / "campaign-runs").exists()


def test_resume_skips_a_cell_completed_in_the_registry(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "resume-app", "RESUME-SPEC-MARKER")
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix = load_matrix_config(
        _matrix_config(tmp_path, [app], builders=builders), repo_root=REPO_ROOT
    )
    cells = plan_matrix(matrix)
    matrix.run.output_root.mkdir(parents=True)
    completed = cells[0]
    (matrix.run.output_root / "registry.jsonl").write_text(
        "".join(
            json.dumps({"arm": arm, "matrix": completed.dimensions}) + "\n"
            for arm in ARMS
        ),
        encoding="utf-8",
    )
    concurrency = _Concurrency()

    result = run_matrix(
        matrix,
        repo_root=REPO_ROOT,
        runner_factory=lambda role: _FakeRunner(role, concurrency),
        metrics_collector=lambda workspace, out_dir: {},
        log=lambda message: None,
    )

    assert result.skipped == (completed,)
    assert len(result.completed) == 1
    assert concurrency.build_calls == 2


def test_resume_does_not_skip_cell_missing_maintenance_rows(tmp_path: Path) -> None:
    app = _add_maintenance(
        tmp_path,
        _single_config(tmp_path, "resume-maintenance-app", "BUILD-SPEC-MARKER"),
        "MAINTENANCE-SPEC-MARKER",
    )
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix = load_matrix_config(
        _matrix_config(
            tmp_path,
            [app],
            builders=builders,
            seeds="[11]",
        ),
        repo_root=REPO_ROOT,
    )
    cell = plan_matrix(matrix)[0]
    matrix.run.output_root.mkdir(parents=True)
    (matrix.run.output_root / "registry.jsonl").write_text(
        "".join(
            json.dumps({"arm": arm, "phase": "build", "matrix": cell.dimensions}) + "\n"
            for arm in ARMS
        ),
        encoding="utf-8",
    )
    concurrency = _Concurrency()

    result = run_matrix(
        matrix,
        repo_root=REPO_ROOT,
        runner_factory=lambda role: _FakeRunner(role, concurrency),
        metrics_collector=lambda workspace, out_dir: {},
        log=lambda message: None,
    )

    assert result.skipped == ()
    assert result.completed == (cell,)
    assert concurrency.build_calls == 4


def test_builder_and_judge_must_obey_family_disjointness_rule(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "family-app", "FAMILY-SPEC-MARKER")
    builders = """
[[builders]]
provider = "codex"
model = "gpt-builder"
"""
    judge = """
[judge]

[[judge.panel]]
provider = "codex"
model = "gpt-judge"
"""

    with pytest.raises(ConfigError, match="family-disjointness rule.*gpt"):
        load_matrix_config(
            _matrix_config(tmp_path, [app], builders=builders, judge=judge),
            repo_root=REPO_ROOT,
        )


def test_unknown_variant_is_rejected_before_output_is_created(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "variant-app", "VARIANT-SPEC-MARKER")
    matrix_path = _matrix_config(tmp_path, [app], variants='["missing-variant"]')

    with pytest.raises(ConfigError, match="unknown template variant.*missing-variant"):
        load_matrix_config(matrix_path, repo_root=REPO_ROOT)

    assert not (tmp_path / "campaign-runs").exists()


def test_matrix_variant_replaces_app_named_variant_answers(tmp_path: Path) -> None:
    app = _single_config(tmp_path, "variant-app", "VARIANT-SPEC-MARKER")
    app.write_text(
        app.read_text(encoding="utf-8").replace(
            'variant = "baseline"', 'variant = "no-precommit"'
        ),
        encoding="utf-8",
    )
    builders = """
[[builders]]
provider = "claude"
model = "claude-test"
"""
    matrix = load_matrix_config(
        _matrix_config(
            tmp_path,
            [app],
            builders=builders,
            variants='["no-agents-md"]',
            seeds="[11]",
        ),
        repo_root=REPO_ROOT,
    )

    template = plan_matrix(matrix)[0].config.template

    assert template.variant == "no-agents-md"
    assert template.answers == {"agents_contract": "none"}
