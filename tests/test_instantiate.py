"""Tests for instantiate.py, the template generator.

These tests exercise the generator only. The full downstream quality gate is
covered by scripts/validate_pack.py (run through 'just validate').
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

from copier import run_copy
import pytest

# Import paths are provided by tests/conftest.py.
import instantiate
from validate_pack import find_forbidden_artifacts, find_unrendered_jinja

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANTIATE = REPO_ROOT / "instantiate.py"
TEMPLATE = REPO_ROOT / "template"
COPIER_CONFIG = REPO_ROOT / "copier.yml"

PROJECT_NAME = "acme-orders"
PACKAGE_NAME = "acme_orders"
EXPECTED_TEMPLATE_SOURCE = "https://github.com/feltroidprime/python-design-guardrails-pack.git"
SESSION_PROFILER_DEPENDENCY = (
    "session-profiler-optimizer @ "
    "git+https://github.com/feltroidprime/session-profiler-optimizer.git"
    "@6ace879e8642777658576a47e0f53b32a1ddc0f7"
)
INVALID_PROJECT_NAMES = ("My-Product", "-orders", "orders app", "orders/app", "")
INVALID_PACKAGE_NAMES = ("1orders", "acme-orders", "Acme", "acme orders", "")

EXPECTED_FILES = (
    ".repo/capabilities/repository_generation.toml",
    ".repo/repository.toml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/quality.yml",
    ".gitignore",
    "prek.toml",
    ".python-version",
    ".vscode/settings.json",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "architecture.toml",
    "docs/README.md",
    "docs/adr/0000-template.md",
    "docs/adr/0001-foundation-ports-and-reference-adapters.md",
    "docs/adr/0002-agent-native-cli-protocol.md",
    "docs/adr/0003-agent-session-evidence.md",
    "docs/adr/0004-agent-input-retry-and-composition-contract.md",
    "docs/adr/0005-review-finding-checks.md",
    "docs/adr/0006-proof-carrying-core.md",
    "docs/architecture/EXCEPTIONS.md",
    "docs/architecture/PROVABILITY.md",
    "justfile",
    "proof/foundation.toml",
    "proof/_generated/index.json",
    "proof/policy.toml",
    "proof/repoctl/repository-generation.toml",
    "pyproject.toml",
    "repoctl/__init__.py",
    "repoctl/modules/__init__.py",
    "repoctl/modules/repository_generation/__init__.py",
    "repoctl/modules/repository_generation/adapters/__init__.py",
    "repoctl/modules/repository_generation/adapters/inbound/__init__.py",
    "repoctl/modules/repository_generation/adapters/outbound/__init__.py",
    "repoctl/modules/repository_generation/api.py",
    "repoctl/modules/repository_generation/application/__init__.py",
    "repoctl/modules/repository_generation/domain/__init__.py",
    "repoctl/modules/repository_generation/domain/decisions.py",
    "repoctl/modules/repository_generation/domain/indexes.py",
    "repoctl/modules/repository_generation/domain/intents.py",
    "repoctl/modules/repository_generation/domain/ownership.py",
    "repoctl/modules/repository_generation/domain/plans.py",
    "repoctl/modules/repository_generation/domain/plans_planner.py",
    "repoctl/modules/repository_generation/domain/specifications.py",
    "scripts/architecture_guard.py",
    "scripts/architecture_rules.py",
    "scripts/capability_validator.py",
    "scripts/__init__.py",
    "scripts/agent_sessions.py",
    "scripts/cli_discipline.py",
    "scripts/crosshair_gate.py",
    "scripts/docs_guard.py",
    "scripts/doctor.py",
    "scripts/none_discipline.py",
    "scripts/ownership.py",
    "scripts/ownership_guard.py",
    "scripts/ownership_policy.py",
    "scripts/override_discipline.py",
    "scripts/proof_assertions.py",
    "scripts/proof_ast.py",
    "scripts/proof_catalog.py",
    "scripts/proof_catalog_model.py",
    "scripts/proof_catalog_schema.py",
    "scripts/proof_discovery.py",
    "scripts/proof_evidence_rules.py",
    "scripts/proof_guard.py",
    "scripts/proof_guard_model.py",
    "scripts/proof_invocations.py",
    "scripts/proof_model.py",
    "scripts/proof_oracle_rules.py",
    "scripts/proof_reexports.py",
    "scripts/proof_sources.py",
    "scripts/proof_stateful.py",
    "scripts/proof_target_rules.py",
    "scripts/proof_tests.py",
    "scripts/quality_gate.py",
    "scripts/review_discipline.py",
    "tests/e2e/session_contract.py",
    "tests/e2e/test_real_agent_sessions.py",
    f"src/{PACKAGE_NAME}/__main__.py",
    f"src/{PACKAGE_NAME}/_generated/active_capabilities.py",
    f"src/{PACKAGE_NAME}/_generated/cli_catalog.py",
    f"src/{PACKAGE_NAME}/_generated/composition.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_catalog.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_contract.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_outcomes.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_protocol.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_runtime.py",
    f"src/{PACKAGE_NAME}/adapters/outbound/sqlite_repository.py",
    f"src/{PACKAGE_NAME}/application/errors.py",
    f"src/{PACKAGE_NAME}/application/idempotency.py",
    f"src/{PACKAGE_NAME}/application/query_models.py",
    f"src/{PACKAGE_NAME}/application/specifications.py",
    f"src/{PACKAGE_NAME}/bootstrap.py",
    f"src/{PACKAGE_NAME}/domain/decisions.py",
    f"src/{PACKAGE_NAME}/domain/entities.py",
    f"src/{PACKAGE_NAME}/domain/events.py",
    f"src/{PACKAGE_NAME}/domain/specifications.py",
    f"src/{PACKAGE_NAME}/domain/value_objects.py",
    f"src/{PACKAGE_NAME}/py.typed",
    "tests/contract/item_repository_contract.py",
    "tests/contract/cli_case_primitives.py",
    "tests/contract/cli_contract_cases.py",
    "tests/contract/cli_outcome_cases.py",
    "tests/integration/test_cli_case_shapes.py",
    "tests/integration/test_cli_contract.py",
    "tests/e2e/test_session_evidence.py",
    "tests/integration/test_cli_composability.py",
    "tests/integration/test_cli_discovery.py",
    "tests/integration/test_cli_idempotency.py",
    "tests/integration/test_cli_input_contract.py",
    "tests/integration/test_cli_outcomes.py",
    "tests/integration/test_cli_safety_contract.py",
    "tests/repoctl/test_draft_capsule.py",
    "tests/repoctl/unit/test_plan_models.py",
    "tests/unit/adapters/test_cli_protocol.py",
    "tests/unit/domain/test_value_objects.py",
    "verification/conftest.py",
    "verification/harness/assertions.py",
    "verification/harness/stateful.py",
    "verification/harness/strategies.py",
    "verification/harness/symbolic_canary.py",
    "verification/repoctl/test_derived_index_properties.py",
    "verification/repoctl/test_path_closed_properties.py",
    "verification/repoctl/test_plan_deterministic_properties.py",
    "verification/repoctl/test_proof_policy.py",
    "verification/tests/test_create_item_state_machine.py",
    "verification/tests/test_decision_properties.py",
    "verification/tests/test_domain_state_properties.py",
    "verification/tests/test_repoctl_evidence.py",
    "verification/tests/test_value_object_properties.py",
)


def run_instantiate(
    project: str,
    package: str,
    output: Path,
    *,
    script: Path = INSTANTIATE,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(script), project, package, str(output)]
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.fixture(scope="session")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One shared successful instantiation for read-only assertions."""
    output = tmp_path_factory.mktemp("generated") / PROJECT_NAME
    result = run_instantiate(PROJECT_NAME, PACKAGE_NAME, output)
    assert result.returncode == 0, result.stdout + result.stderr
    return output


def test_valid_generation_reports_success_and_next_steps(generated: Path) -> None:
    # The fixture already asserts exit code 0; re-run into a fresh directory
    # to assert the printed contract.
    fresh = generated.parent / "fresh-copy"
    result = run_instantiate(PROJECT_NAME, PACKAGE_NAME, fresh)
    assert result.returncode == 0
    assert f"Created {PROJECT_NAME}" in result.stdout
    assert "just bootstrap" in result.stdout


def test_generated_repository_uses_prek_for_git_hooks(generated: Path) -> None:
    config = tomllib.loads((generated / "prek.toml").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((generated / "pyproject.toml").read_text(encoding="utf-8"))
    justfile = (generated / "justfile").read_text(encoding="utf-8")
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}

    assert config["minimum_prek_version"] == "0.4.9"
    assert config["default_install_hook_types"] == ["pre-commit", "pre-push"]
    assert set(hooks) >= {
        "architecture-guard",
        "proof-contract",
        "full-quality-gate",
        "ruff-check",
        "ruff-format",
        "uv-lock",
    }
    assert "prek>=0.4.9" in pyproject["dependency-groups"]["dev"]
    assert "uv run prek install -f" in justfile
    assert "uv run prek update" in justfile
    assert "uv run pre-commit" not in justfile
    assert hooks["full-quality-gate"]["entry"].endswith("python scripts/quality_gate.py")


def test_generated_baseline_files_pass_data_and_eof_hooks(generated: Path) -> None:
    json.loads((generated / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    assert (generated / "CLAUDE.md").read_bytes().endswith(b"\n")


def test_generated_justfile_has_one_routine_gate_and_one_private_e2e_route(
    generated: Path,
) -> None:
    justfile = (generated / "justfile").read_text(encoding="utf-8")

    assert re.findall(r"(?m)^([a-z][a-z0-9-]*):(?:\s|$)", justfile) == [
        "default",
        "bootstrap",
        "check",
        "prove",
        "prove-deep",
        "proof-report",
        "doctor",
        "session-e2e",
        "scaffold-update",
        "update",
    ]
    assert re.findall(r"(?m)^([a-z][a-z0-9-]*) [^:\n]+:$", justfile) == [
        "prove-one",
        "session-log",
    ]
    assert re.search(r"(?m)^prove-one property_id:$", justfile) is not None
    assert "uv run python scripts/quality_gate.py --fix" in justfile
    assert "uv run python -m scripts.proof_guard" in justfile
    assert "uv run python -m scripts.crosshair_gate fast" in justfile
    assert '--property-id "$1"' in justfile
    assert "HYPOTHESIS_PROFILE=fast" in justfile
    assert (
        "env -u PYTHONPYCACHEPREFIX uvx --from copier==9.17.0 copier update "
        "--defaults --conflict inline" in justfile
    )
    assert justfile.count('uv run --with "$SESSION_PROFILER_DEPENDENCY" pytest') == 1
    assert "-m session_e2e" in justfile
    assert "scripts.architecture_guard" not in justfile


def test_generated_gate_rejects_tracked_unimported_python_syntax(
    tmp_path: Path,
) -> None:
    project = _generate_with_answers(tmp_path / "syntax-gate", {})
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main"],
        cwd=project,
        check=True,
    )
    planted = project / "unimported_syntax_error.py"
    planted.write_text(
        "def unseen(:\n    pass\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "--all"], cwd=project, check=True)

    result = subprocess.run(
        [sys.executable, "scripts/quality_gate.py", "--fix"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "=== tracked Python syntax ===" in result.stdout
    assert "unimported_syntax_error.py:1" in result.stderr
    assert "SyntaxError" in result.stderr
    assert "=== safe lint repairs ===" not in result.stdout


def test_generated_gate_names_hook_repair_before_any_other_output(
    tmp_path: Path,
) -> None:
    project = _generate_with_answers(tmp_path / "hook-failure", {})
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main"],
        cwd=project,
        check=True,
    )
    bin_dir = tmp_path / "hook-failure-bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/bin/sh\nprintf 'uv unavailable\\n' >&2\nexit 41\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        [sys.executable, "scripts/quality_gate.py", "--fix"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 41
    assert result.stdout == ""
    assert result.stderr.splitlines()[0] == "uv run prek install -f"
    assert "uv unavailable" in result.stderr


def test_generated_doctor_reports_green_then_detects_a_dirty_working_tree(
    tmp_path: Path,
) -> None:
    project = _generate_with_answers(tmp_path / "doctor-green", {})
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main"],
        cwd=project,
        check=True,
    )
    hooks = project / ".git" / "hooks"
    for hook_type in ("pre-commit", "pre-push"):
        hook = hooks / hook_type
        hook.write_text(
            "#!/bin/sh\n"
            "# File generated by prek: test fixture\n"
            f"# --hook-type={hook_type}\n"
            "exit 0\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)
    (project / ".python-version").write_text(
        f"{sys.version_info.major}.{sys.version_info.minor}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "--all"], cwd=project, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            "--message=bootstrapped baseline",
        ],
        cwd=project,
        check=True,
    )

    bin_dir = tmp_path / "doctor-bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "run" ] && [ "$2" = "--no-sync" ] '
        '&& [ "$3" = "python" ]; then\n'
        "  shift 3\n"
        f'  exec "{sys.executable}" "$@"\n'
        "fi\n"
        'if [ "$1" = "sync" ] && [ "$2" = "--check" ]; then exit 0; fi\n'
        "exit 64\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\nprintf 'network is unreachable\\n' >&2\nexit 1\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["just", "doctor"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 7
    assert lines[0].startswith("ok hooks:")
    assert lines[1] == "ok working-tree: clean"
    assert lines[2].startswith("warn branch-sync: skipped:")
    assert lines[3].startswith("warn gh-auth: skipped:")
    assert lines[4].startswith("ok uv-sync:")
    assert lines[5].startswith("ok python-version:")
    assert lines[6] == "ok verdict: 0 failures, 2 warnings"

    (project / "doctor-dirty-probe.txt").write_text("fault\n", encoding="utf-8")
    dirty_result = subprocess.run(
        ["just", "doctor"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert dirty_result.returncode == 1
    dirty_lines = dirty_result.stdout.splitlines()
    assert dirty_lines[1] == "fail working-tree: dirty (1 entries)"
    assert dirty_lines[-1] == "fail verdict: 1 failures, 2 warnings"


def test_generated_repository_can_preserve_complete_agent_sessions(
    generated: Path,
) -> None:
    pyproject = tomllib.loads((generated / "pyproject.toml").read_text(encoding="utf-8"))
    justfile = (generated / "justfile").read_text(encoding="utf-8")
    gitignore = (generated / ".gitignore").read_text(encoding="utf-8").splitlines()
    dependencies = pyproject["dependency-groups"]["dev"]

    assert SESSION_PROFILER_DEPENDENCY not in dependencies
    assert not any(dependency.startswith("harbor") for dependency in dependencies)
    assert not any(dependency.startswith("litellm") for dependency in dependencies)
    assert justfile.count(SESSION_PROFILER_DEPENDENCY) == 1
    assert 'session-log input output=".agent-sessions" agent="auto":' in justfile
    assert 'uv run --with "$SESSION_PROFILER_DEPENDENCY" session-profiler' in justfile
    assert "session-e2e:" in justfile
    assert 'uv run --with "$SESSION_PROFILER_DEPENDENCY" pytest' in justfile
    assert "not session_e2e" in pyproject["tool"]["pytest"]["ini_options"]["addopts"]
    assert ".agent-sessions/" in gitignore
    assert "output/" not in gitignore


def test_scaffold_update_does_not_create_an_invalid_project_venv(
    tmp_path: Path,
) -> None:
    project = _generate_with_answers(tmp_path / "project", {})
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uvx = bin_dir / "uvx"
    uvx.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        '[[ -z "${PYTHONPYCACHEPREFIX+x}" ]]\n'
        '[[ "$*" == "--from copier==9.17.0 copier update --defaults '
        '--conflict inline" ]]\n',
        encoding="utf-8",
    )
    uvx.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["just", "scaffold-update"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (project / ".venv").exists()


def test_generation_records_copier_template_and_answers(generated: Path) -> None:
    answers = (generated / ".copier-answers.yml").read_text(encoding="utf-8")

    assert re.search(
        rf"(?m)^_src_path: ['\"]?{re.escape(EXPECTED_TEMPLATE_SOURCE)}['\"]?$",
        answers,
    )
    assert re.search(r"(?m)^_commit: .+$", answers)
    assert re.search(rf"(?m)^project_name: ['\"]?{PROJECT_NAME}['\"]?$", answers)
    assert re.search(rf"(?m)^package: ['\"]?{PACKAGE_NAME}['\"]?$", answers)


def test_generated_readme_documents_copier_update_workflow(generated: Path) -> None:
    readme = (generated / "README.md").read_text(encoding="utf-8")

    assert "`python-repo init` runs this recipe before creating the baseline commit" in readme
    assert "Linked worktrees created with `git worktree add`" in readme
    assert "uvx --from copier==9.17.0 copier check-update --quiet" in readme
    assert "exit status `2`" in readme
    assert "just scaffold-update" in readme
    assert "check-merge-conflict" in readme


def test_generated_agent_contract_routes_scaffold_updates(generated: Path) -> None:
    contract = (generated / "AGENTS.md").read_text(encoding="utf-8")

    assert "`just scaffold-update`" in contract
    assert "`just update` remains dependency-only" in contract
    assert "Resolve Copier conflicts" in contract


def test_generated_readiness_docs_route_doctor_before_publication(
    generated: Path,
) -> None:
    readme = (generated / "README.md").read_text(encoding="utf-8")
    contract = (generated / "AGENTS.md").read_text(encoding="utf-8")

    assert "Run `just doctor` immediately before deployment or publication" in readme
    assert "Every `fail` blocks the operation" in contract
    assert "`warn` is reserved for an explicitly unavailable check" in contract


def test_copier_migrations_are_wired() -> None:
    config = COPIER_CONFIG.read_text(encoding="utf-8")

    assert "_migrations: []" in config


def test_fast_recipe_renders_default_template_and_runs_policy_checks() -> None:
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    recipe = re.search(
        r"(?ms)^test-fast:(?P<dependencies>[^\n]*)\n(?P<body>(?:    .+\n)+)",
        justfile,
    )

    assert recipe is not None
    assert recipe.group("dependencies").split() == ["check"]
    for required_test in (
        "tests/test_instantiate.py::test_expected_files_are_preserved",
        "tests/test_instantiate.py::test_no_unrendered_jinja_survives",
        "tests/test_instantiate.py::test_fast_recipe_renders_default_template_and_runs_policy_checks",
        "tests/test_pin_coherence.py",
        "tests/test_hook_policy.py",
        "tests/test_root_ruff_policy.py",
    ):
        assert required_test in recipe.group("body")


def _generate_with_answers(output: Path, answers: dict[str, object]) -> Path:
    with instantiate.without_local_git_context():
        run_copy(
            str(REPO_ROOT),
            output,
            data={
                "project_name": PROJECT_NAME,
                "package": PACKAGE_NAME,
                **answers,
            },
            vcs_ref="HEAD",
            defaults=True,
            quiet=True,
            skip_tasks=True,
        )
    return output


def _generated_snapshot(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        if relative == ".copier-answers.yml":
            content = re.sub(rb"(?m)^_commit: .+$", b"_commit: <resolved>", content)
        snapshot[relative] = content
    return snapshot


def test_delta_or_identical_explicit_default_toggles_are_byte_identical_to_defaults(
    tmp_path: Path,
) -> None:
    implicit = _generate_with_answers(tmp_path / "implicit", {})
    explicit = _generate_with_answers(
        tmp_path / "explicit",
        {"agents_contract": "full"},
    )

    assert _generated_snapshot(implicit) == _generated_snapshot(explicit)


def test_delta_or_identical_workspace_member_has_exact_file_delta(
    tmp_path: Path,
) -> None:
    baseline = _generated_snapshot(_generate_with_answers(tmp_path / "baseline", {}))
    variant = _generated_snapshot(
        _generate_with_answers(tmp_path / "workspace-member", {"workspace_member": True})
    )

    assert set(baseline) - set(variant) == {".python-version", "prek.toml"}
    assert set(variant) - set(baseline) == set()
    assert {path for path in set(baseline) & set(variant) if baseline[path] != variant[path]} == {
        ".copier-answers.yml",
        "README.md",
        "justfile",
        "pyproject.toml",
    }

    pyproject = tomllib.loads(variant["pyproject.toml"].decode("utf-8"))
    # The workspace root owns the dev group and the shared tool config; a member
    # keeps only its build system, project metadata, the uv pin, and its own
    # per-package import-linter contracts.
    assert "dependency-groups" not in pyproject
    assert set(pyproject["tool"]) == {"uv", "importlinter"}
    assert {contract["id"] for contract in pyproject["tool"]["importlinter"]["contracts"]} == {
        "layers",
        "adapter-independence",
    }

    justfile = variant["justfile"].decode("utf-8")
    assert "uv sync" not in justfile
    assert "uv lock" not in justfile
    assert "prek" not in justfile
    assert "just check" in justfile


def test_delta_or_identical_no_agents_md_has_exact_file_delta(tmp_path: Path) -> None:
    baseline = _generated_snapshot(_generate_with_answers(tmp_path / "baseline", {}))
    variant = _generated_snapshot(
        _generate_with_answers(tmp_path / "no-agents-md", {"agents_contract": "none"})
    )

    assert set(baseline) - set(variant) == {"AGENTS.md", "CLAUDE.md"}
    assert set(variant) - set(baseline) == set()
    assert {path for path in set(baseline) & set(variant) if baseline[path] != variant[path]} == {
        ".copier-answers.yml",
        "README.md",
        "docs/README.md",
    }
    for path in ("README.md", "docs/README.md"):
        assert b"AGENTS.md" not in variant[path]
        assert b"CLAUDE.md" not in variant[path]


def test_checks_via_commit_has_exact_agents_content_delta(tmp_path: Path) -> None:
    baseline = _generated_snapshot(_generate_with_answers(tmp_path / "baseline", {}))
    variant = _generated_snapshot(
        _generate_with_answers(
            tmp_path / "checks-via-commit",
            {"agents_contract": "hooks-first"},
        )
    )

    assert set(baseline) == set(variant)
    assert {path for path in baseline if baseline[path] != variant[path]} == {
        ".copier-answers.yml",
        "AGENTS.md",
    }

    expected_agents = baseline["AGENTS.md"].replace(
        b"6. Green means the unmodified gate exits zero. Then report the property IDs changed, "
        b"counterexamples considered, architecture impact, external assumptions, and remaining "
        b"risks.\n\n",
        b"6. Green means the unmodified gate exits zero. Then report the property IDs changed, "
        b"counterexamples considered, architecture impact, external assumptions, and remaining "
        b"risks.\n"
        b"7. Commit and push. Publication is complete when the commit and pre-push hooks succeed "
        b"and `just doctor` reports no failures.\n\n",
    )
    assert variant["AGENTS.md"] == expected_agents


def test_copier_derives_package_default_from_project_name(tmp_path: Path) -> None:
    output = tmp_path / "default-answer"

    with instantiate.without_local_git_context():
        run_copy(
            str(REPO_ROOT),
            output,
            data={"project_name": PROJECT_NAME},
            vcs_ref="HEAD",
            defaults=True,
            quiet=True,
            skip_tasks=True,
        )

    assert (output / "src" / PACKAGE_NAME).is_dir()
    assert re.search(
        rf"(?m)^package: ['\"]?{PACKAGE_NAME}['\"]?$",
        (output / ".copier-answers.yml").read_text(encoding="utf-8"),
    )


@pytest.mark.parametrize("project", INVALID_PROJECT_NAMES)
def test_invalid_project_names_are_rejected(project: str, tmp_path: Path) -> None:
    result = run_instantiate(project, PACKAGE_NAME, tmp_path / "out")
    assert result.returncode == 2
    assert "Project name" in result.stdout
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("package", INVALID_PACKAGE_NAMES)
def test_invalid_package_names_are_rejected(package: str, tmp_path: Path) -> None:
    result = run_instantiate(PROJECT_NAME, package, tmp_path / "out")
    assert result.returncode == 2
    assert "Package name" in result.stdout
    assert not (tmp_path / "out").exists()


def test_refuses_to_overwrite_non_empty_directory(tmp_path: Path) -> None:
    output = tmp_path / "occupied"
    output.mkdir()
    sentinel = output / "precious.txt"
    sentinel.write_text("do not touch", encoding="utf-8")

    result = run_instantiate(PROJECT_NAME, PACKAGE_NAME, output)

    assert result.returncode == 2
    assert "Refusing to overwrite" in result.stdout
    assert sentinel.read_text(encoding="utf-8") == "do not touch"
    assert list(output.iterdir()) == [sentinel]


def run_cli(
    *args: str, script: Path = INSTANTIATE, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the `python-repo`-style subcommand interface of instantiate.py."""
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def make_gh_stub(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """PATH-prepend a fake `gh` that records its arguments instead of hitting GitHub."""
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir(exist_ok=True)
    recorded = tmp_path / "gh-args.txt"
    stub = stub_dir / "gh"
    stub.write_text(f'#!/bin/sh\necho "$@" > "{recorded}"\n', encoding="utf-8")
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    return env, recorded


def add_just_stub(tmp_path: Path, env: dict[str, str] | None = None) -> tuple[dict[str, str], Path]:
    """PATH-prepend a bootstrap stand-in that installs shared Git hook shims."""
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir(exist_ok=True)
    recorded = tmp_path / "just-args.txt"
    stub = stub_dir / "just"
    stub.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        f'printf "%s\\n" "$*" > "{recorded}"\n'
        'test "$*" = "bootstrap"\n'
        "git rev-parse --is-inside-work-tree >/dev/null\n"
        "if git rev-parse --verify HEAD >/dev/null 2>&1; then\n"
        "  exit 42\n"
        "fi\n"
        'hooks="$(git rev-parse --git-path hooks)"\n'
        'mkdir -p "$hooks"\n'
        "for hook in pre-commit pre-push; do\n"
        '  printf "#!/bin/sh\\nexit 0\\n" > "$hooks/$hook"\n'
        '  chmod +x "$hooks/$hook"\n'
        "done\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    environment = dict(os.environ if env is None else env)
    environment["PATH"] = f"{stub_dir}{os.pathsep}{environment['PATH']}"
    return environment, recorded


def copy_pack(destination: Path) -> Path:
    destination.mkdir()
    shutil.copy(INSTANTIATE, destination / "instantiate.py")
    shutil.copy(COPIER_CONFIG, destination / "copier.yml")
    shutil.copytree(TEMPLATE, destination / "template")
    return destination


def snapshot_working_tree(repository: Path) -> dict[str, bytes]:
    """Capture every working-tree file without traversing Git's metadata."""
    snapshot: dict[str, bytes] = {}
    for directory, names, files in os.walk(repository):
        names[:] = [name for name in names if name != ".git"]
        root = Path(directory)
        for filename in files:
            path = root / filename
            snapshot[path.relative_to(repository).as_posix()] = path.read_bytes()
    return snapshot


def test_init_bootstraps_before_first_commit_and_hooks_cover_worktrees(tmp_path: Path) -> None:
    environment, bootstrap_args = add_just_stub(tmp_path)
    result = run_cli("init", PROJECT_NAME, str(tmp_path), "--no-github", env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    target = tmp_path / PROJECT_NAME
    assert (target / "src" / PACKAGE_NAME).is_dir(), "package name was not derived"
    assert f"Created {PROJECT_NAME}" in result.stdout
    assert "just bootstrap" not in result.stdout
    assert bootstrap_args.read_text(encoding="utf-8") == "bootstrap\n"
    assert (target / ".git").is_dir(), "git repository was not initialized"
    head = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=target,
        env=instantiate.environment_without_local_git_context(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert head.returncode == 0, head.stderr
    assert head.stdout.count("\n") == 1, "expected one initial commit"

    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "worktree", "add", "--quiet", "--detach", str(linked)],
        cwd=target,
        env=instantiate.environment_without_local_git_context(),
        check=True,
    )
    for hook in ("pre-commit", "pre-push"):
        primary_hook = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-path", f"hooks/{hook}"],
            cwd=target,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        linked_hook = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-path", f"hooks/{hook}"],
            cwd=linked,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert linked_hook == primary_hook
        assert os.access(linked_hook, os.X_OK)
        arguments = [linked_hook]
        if hook == "pre-push":
            arguments.extend(("origin", "unused"))
        assert subprocess.run(arguments, cwd=linked, check=False).returncode == 0


def test_init_stops_before_commit_and_github_when_bootstrap_fails(tmp_path: Path) -> None:
    environment, github_args = make_gh_stub(tmp_path)
    environment, bootstrap_args = add_just_stub(tmp_path, environment)
    just = tmp_path / "stub-bin" / "just"
    just.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" > "{bootstrap_args}"\nexit 23\n',
        encoding="utf-8",
    )
    just.chmod(0o755)
    result = run_cli("init", PROJECT_NAME, str(tmp_path), env=environment)

    assert result.returncode == 1
    assert "Bootstrap failed: 'just bootstrap' exited with 23." in result.stdout
    assert "Repository left incomplete at" in result.stdout
    assert f"Created {PROJECT_NAME}" not in result.stdout
    assert not github_args.exists()
    target = tmp_path / PROJECT_NAME
    assert (target / ".git").is_dir()
    assert (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=target,
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )


def test_init_honors_explicit_package_name(tmp_path: Path) -> None:
    result = run_cli("init", PROJECT_NAME, str(tmp_path), "--package", "customcore", "--no-git")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / PROJECT_NAME / "src" / "customcore").is_dir()


def test_init_no_git_skips_git_and_github(tmp_path: Path) -> None:
    result = run_cli("init", PROJECT_NAME, str(tmp_path), "--no-git")
    assert result.returncode == 0, result.stdout + result.stderr
    target = tmp_path / PROJECT_NAME
    assert not (target / ".git").exists()
    assert find_unrendered_jinja(target) == []


def test_init_creates_private_github_repository_by_default(tmp_path: Path) -> None:
    env, recorded = make_gh_stub(tmp_path)
    env, _ = add_just_stub(tmp_path, env)
    result = run_cli("init", PROJECT_NAME, str(tmp_path / "work"), env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert recorded.read_text(encoding="utf-8").split() == [
        "repo",
        "create",
        PROJECT_NAME,
        "--private",
        "--source",
        ".",
        "--remote",
        "origin",
        "--push",
    ]


def test_init_public_flag_flips_github_visibility(tmp_path: Path) -> None:
    env, recorded = make_gh_stub(tmp_path)
    env, _ = add_just_stub(tmp_path, env)
    result = run_cli("init", PROJECT_NAME, str(tmp_path / "work"), "--public", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--public" in recorded.read_text(encoding="utf-8").split()
    assert "--private" not in recorded.read_text(encoding="utf-8").split()


def test_init_failing_gh_reports_manual_command_and_exit_1(tmp_path: Path) -> None:
    env, _ = make_gh_stub(tmp_path)
    env, _ = add_just_stub(tmp_path, env)
    stub = tmp_path / "stub-bin" / "gh"
    stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    result = run_cli("init", PROJECT_NAME, str(tmp_path / "work"), env=env)
    assert result.returncode == 1
    assert "GitHub repository creation failed" in result.stdout
    assert f"gh repo create {PROJECT_NAME} --private" in result.stdout
    # The local repository is still usable.
    assert (tmp_path / "work" / PROJECT_NAME / ".git").is_dir()


def test_init_rejects_underivable_package_name(tmp_path: Path) -> None:
    result = run_cli("init", "1orders", str(tmp_path), "--no-git")
    assert result.returncode == 2
    assert "--package" in result.stdout
    assert not (tmp_path / "1orders").exists()


def test_init_refuses_existing_non_empty_target(tmp_path: Path) -> None:
    occupied = tmp_path / PROJECT_NAME
    occupied.mkdir()
    (occupied / "precious.txt").write_text("do not touch", encoding="utf-8")
    result = run_cli("init", PROJECT_NAME, str(tmp_path), "--no-git")
    assert result.returncode == 2
    assert "Refusing to overwrite" in result.stdout


def test_package_directory_is_rendered(generated: Path) -> None:
    assert (generated / "src" / PACKAGE_NAME).is_dir()
    assert not (generated / "src" / "{{ package }}").exists()


def test_no_unrendered_jinja_survives(generated: Path) -> None:
    leftovers = find_unrendered_jinja(generated)
    assert leftovers == [], "Unrendered Jinja:\n" + "\n".join(leftovers)


def test_unrendered_scan_rejects_stray_jinja_suffix(tmp_path: Path) -> None:
    (tmp_path / "missed.txt.jinja").write_text("plain text\n", encoding="utf-8")

    assert find_unrendered_jinja(tmp_path) == ["missed.txt.jinja: stray .jinja template suffix"]


def test_unrendered_scan_detects_jinja_whitespace_control(tmp_path: Path) -> None:
    (tmp_path / "missed.txt").write_text("{{- package }}\n{%- if package %}\n", encoding="utf-8")

    assert find_unrendered_jinja(tmp_path) == [
        "missed.txt:1: contains Jinja syntax",
        "missed.txt:2: contains Jinja syntax",
    ]


def test_template_itself_contains_no_local_artifacts() -> None:
    artifacts = find_forbidden_artifacts(TEMPLATE)
    assert artifacts == [], (
        "template/ contains local runtime artifacts that would leak into every "
        "generated repository:\n" + "\n".join(str(path) for path in artifacts)
    )


def test_planted_cache_artifacts_never_reach_generated_repository(tmp_path: Path) -> None:
    """Even a dirty template copy must produce a clean repository."""
    pack_copy = copy_pack(tmp_path / "pack")

    ruff_cache = pack_copy / "template" / ".ruff_cache" / "0.15.21"
    ruff_cache.mkdir(parents=True)
    (ruff_cache / "1234").write_bytes(b"\x00cache")
    pycache = pack_copy / "template" / "scripts" / "__pycache__"
    pycache.mkdir()
    (pycache / "quality_gate.cpython-314.pyc").write_bytes(b"\x00pyc")
    (pack_copy / "template" / ".DS_Store").write_bytes(b"\x00junk")

    output = tmp_path / "out"
    result = run_instantiate(
        PROJECT_NAME, PACKAGE_NAME, output, script=pack_copy / "instantiate.py"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    artifacts = find_forbidden_artifacts(output)
    assert artifacts == [], "Cache artifacts leaked into the generated repository:\n" + "\n".join(
        str(path) for path in artifacts
    )


def test_undefined_jinja_variable_fails_generation_loudly(tmp_path: Path) -> None:
    pack_copy = copy_pack(tmp_path / "pack")
    (pack_copy / "template" / "broken.txt.jinja").write_text(
        "{{ missing_answer }}\n", encoding="utf-8"
    )

    result = run_instantiate(
        PROJECT_NAME, PACKAGE_NAME, tmp_path / "out", script=pack_copy / "instantiate.py"
    )

    assert result.returncode != 0
    assert "missing_answer" in result.stdout + result.stderr


def test_generation_uses_current_dirty_worktree_instead_of_latest_tag(
    tmp_path: Path,
) -> None:
    pack_copy = copy_pack(tmp_path / "pack")
    git_env = instantiate.environment_without_local_git_context()
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main"],
        cwd=pack_copy,
        env=git_env,
        check=True,
    )
    subprocess.run(["git", "add", "--all"], cwd=pack_copy, env=git_env, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            "--message=tagged template",
        ],
        cwd=pack_copy,
        env=git_env,
        check=True,
    )
    subprocess.run(["git", "tag", "v0.1.0"], cwd=pack_copy, env=git_env, check=True)
    (pack_copy / "template" / "current-worktree.txt").write_text("current\n", encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=pack_copy, env=git_env, check=True)

    output = tmp_path / "out"
    hook_env = dict(git_env)
    hook_env["GIT_DIR"] = str(pack_copy / ".git")
    hook_env["GIT_INDEX_FILE"] = str(pack_copy / ".git" / "index")
    hook_env["GIT_WORK_TREE"] = str(pack_copy)
    result = run_instantiate(
        PROJECT_NAME,
        PACKAGE_NAME,
        output,
        script=pack_copy / "instantiate.py",
        env=hook_env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output / "current-worktree.txt").read_text(encoding="utf-8") == "current\n"
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=pack_copy,
        env=git_env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert staged.stdout.splitlines() == ["template/current-worktree.txt"]


def test_generation_from_linked_worktree_does_not_modify_primary_checkout(
    tmp_path: Path,
) -> None:
    primary = copy_pack(tmp_path / "primary")
    linked = tmp_path / "linked"
    git_env = instantiate.environment_without_local_git_context()
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main"],
        cwd=primary,
        env=git_env,
        check=True,
    )
    subprocess.run(["git", "add", "--all"], cwd=primary, env=git_env, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            "--message=initial template",
        ],
        cwd=primary,
        env=git_env,
        check=True,
    )
    subprocess.run(
        ["git", "worktree", "add", "--quiet", "--detach", str(linked)],
        cwd=primary,
        env=git_env,
        check=True,
    )
    marker = "linked-worktree-only\n"
    (linked / "template" / "linked-worktree.txt").write_text(marker, encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=linked, env=git_env, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            "--message=linked template change",
        ],
        cwd=linked,
        env=git_env,
        check=True,
    )
    dirty_marker = "dirty-linked-worktree-only\n"
    (linked / "template" / "dirty-linked-worktree.txt").write_text(dirty_marker, encoding="utf-8")

    before = snapshot_working_tree(primary)
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=primary,
            env=git_env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        == ""
    )

    output = tmp_path / "out"
    inherited_git_env = dict(git_env)
    inherited_git_env["GIT_DIR"] = str(primary / ".git")
    inherited_git_env["GIT_INDEX_FILE"] = str(
        primary / ".git" / "worktrees" / linked.name / "index"
    )
    result = run_instantiate(
        PROJECT_NAME,
        PACKAGE_NAME,
        output,
        script=linked / "instantiate.py",
        env=inherited_git_env,
        cwd=linked,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot_working_tree(primary) == before
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=primary,
            env=git_env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        == ""
    )
    assert (output / "linked-worktree.txt").read_text(encoding="utf-8") == marker
    assert (output / "dirty-linked-worktree.txt").read_text(encoding="utf-8") == dirty_marker


def test_packaged_template_records_distribution_version_without_git_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_copy = copy_pack(tmp_path / "installed-pack")
    monkeypatch.setattr(instantiate, "__file__", str(pack_copy / "instantiate.py"))
    monkeypatch.setattr(instantiate, "distribution_version", lambda _name: "1.2.3")

    output = tmp_path / "out"
    assert instantiate.generate(PROJECT_NAME, PACKAGE_NAME, output) is None

    answers = (output / ".copier-answers.yml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^_commit: ['\"]?v1\.2\.3['\"]?$", answers)
    assert re.search(
        rf"(?m)^_src_path: ['\"]?{re.escape(EXPECTED_TEMPLATE_SOURCE)}['\"]?$",
        answers,
    )


def test_artifact_exclusions_have_one_configuration_source() -> None:
    config = COPIER_CONFIG.read_text(encoding="utf-8")
    generator = INSTANTIATE.read_text(encoding="utf-8")

    assert "_exclude:" in config
    assert "IGNORED_ARTIFACT_PATTERNS" not in generator


def test_expected_files_are_preserved(generated: Path) -> None:
    missing = [name for name in EXPECTED_FILES if not (generated / name).is_file()]
    assert missing == [], "Missing expected files in generated repository:\n" + "\n".join(missing)


def test_generated_architecture_guard_runs_and_passes(generated: Path) -> None:
    """The guard runs with the repoctl classifier dependency supplied by the test recipe."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.architecture_guard"],
        cwd=generated,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Architecture guard passed." in result.stdout


def test_generated_docs_guard_runs_and_passes(generated: Path) -> None:
    """The docs guard is stdlib-only, so it must run in the generated repo as-is."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.docs_guard"],
        cwd=generated,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Documentation guard passed." in result.stdout


def declared_runtime_environment(generated: Path) -> list[str]:
    """The interpreter command the generated repository declares for itself.

    Reading the interpreter and the runtime dependencies out of the generated
    metadata keeps the smoke test honest twice over: the slice runs against the
    real runtime contract (contracts are executable, never optional), and the
    run fails if `pyproject.toml` stops declaring something the slice imports.
    """
    metadata = tomllib.loads((generated / "pyproject.toml").read_text(encoding="utf-8"))
    interpreter = (generated / ".python-version").read_text(encoding="utf-8").strip()
    command = ["uv", "run", "--no-project", "--python", interpreter]
    for dependency in metadata["project"]["dependencies"]:
        command += ["--with", dependency]
    return [*command, "python"]


def test_generated_vertical_slice_executes(generated: Path) -> None:
    """The example slice must be importable and behave under the new package name."""
    program = (
        "import io\n"
        "import sys\n"
        "sys.path.insert(0, 'src')\n"
        f"from {PACKAGE_NAME}.adapters.inbound.cli import run\n"
        f"from {PACKAGE_NAME}.bootstrap import memory_application\n"
        "app = memory_application()\n"
        "out, err = io.StringIO(), io.StringIO()\n"
        "code = run(['add', '  Pack check  '], create_item=app.create_item,"
        " list_items=app.list_items, out=out, err=err)\n"
        "assert code == 0, (code, err.getvalue())\n"
        "assert 'Pack check' in out.getvalue(), out.getvalue()\n"
        "code = run(['list'], create_item=app.create_item,"
        " list_items=app.list_items, out=out, err=err)\n"
        "assert code == 0, (code, err.getvalue())\n"
        "print('slice ok')\n"
    )
    result = subprocess.run(
        [*declared_runtime_environment(generated), "-c", program],
        cwd=generated,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "slice ok" in result.stdout
