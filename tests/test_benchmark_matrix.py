"""Deterministic campaign tests: real pipeline, fake agents, no network."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

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


def test_dirty_working_tree_content_is_part_of_the_resume_identity(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "copier.yml").write_text("_subdirectory: template\n", encoding="utf-8")
    (pack / "template").mkdir()
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
