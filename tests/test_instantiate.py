"""Tests for instantiate.py, the template generator.

These tests exercise the generator only. The full downstream quality gate is
covered by scripts/validate_pack.py (run through 'just validate').
"""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import pytest
from copier import run_copy

# Import paths are provided by tests/conftest.py.
import instantiate
from instantiate import generate
from validate_pack import find_forbidden_artifacts, find_unrendered_jinja

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANTIATE = REPO_ROOT / "instantiate.py"
TEMPLATE = REPO_ROOT / "template"
COPIER_CONFIG = REPO_ROOT / "copier.yml"

PROJECT_NAME = "acme-orders"
PACKAGE_NAME = "acme_orders"
EXPECTED_GENERATED_TREE_SHA256 = "b333939a27b4f2d6e8abb0e1a19cc5f9c40f7980bb049f4409ae8d908300bd6b"
EXPECTED_TEMPLATE_SOURCE = (
    "https://github.com/feltroidprime/python-design-guardrails-pack.git"
)
INVALID_PROJECT_NAMES = ("My-Product", "-orders", "orders app", "orders/app", "")
INVALID_PACKAGE_NAMES = ("1orders", "acme-orders", "Acme", "acme orders", "")

EXPECTED_FILES = (
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
    "docs/adr/0001-derived-architecture-diagrams.md",
    "docs/adr/0002-foundation-ports-and-reference-adapters.md",
    "docs/adr/0003-agent-native-cli-protocol.md",
    "docs/architecture/EXCEPTIONS.md",
    "docs/architecture/likec4/generated/baseline-views.c4",
    "docs/architecture/likec4/generated/model.c4",
    "docs/architecture/likec4/likec4.config.json",
    "docs/architecture/likec4/specification.c4",
    "docs/architecture/likec4/views.c4",
    "justfile",
    "pyproject.toml",
    "scripts/architecture_guard.py",
    "scripts/architecture_rules.py",
    "scripts/cli_discipline.py",
    "scripts/docs_guard.py",
    "scripts/none_discipline.py",
    "scripts/quality_gate.py",
    "scripts/sync_architecture_diagrams.py",
    f"src/{PACKAGE_NAME}/__main__.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_catalog.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_protocol.py",
    f"src/{PACKAGE_NAME}/adapters/inbound/cli_runtime.py",
    f"src/{PACKAGE_NAME}/adapters/outbound/sqlite_repository.py",
    f"src/{PACKAGE_NAME}/application/errors.py",
    f"src/{PACKAGE_NAME}/application/query_models.py",
    f"src/{PACKAGE_NAME}/bootstrap.py",
    f"src/{PACKAGE_NAME}/domain/value_objects.py",
    f"src/{PACKAGE_NAME}/py.typed",
    "tests/contract/item_repository_contract.py",
    "tests/contract/cli_contract_cases.py",
    "tests/integration/test_cli_contract.py",
    "tests/unit/adapters/test_cli_protocol.py",
    "tests/unit/domain/test_value_objects.py",
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
    return subprocess.run(
        [sys.executable, str(script), project, package, str(output)],
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


def test_generated_justfile_has_one_repair_and_verification_route(generated: Path) -> None:
    justfile = (generated / "justfile").read_text(encoding="utf-8")

    assert re.findall(r"(?m)^([a-z][a-z-]*):(?:\s|$)", justfile) == [
        "default",
        "bootstrap",
        "check",
        "diagrams",
        "scaffold-update",
        "update",
    ]
    assert "uv run python scripts/quality_gate.py --fix" in justfile
    assert (
        "uvx --from copier==9.17.0 copier update --conflict inline" in justfile
    )
    assert "uv run pytest" not in justfile
    assert "scripts.architecture_guard" not in justfile


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

    assert "uvx --from copier==9.17.0 copier check-update --quiet" in readme
    assert "exit status `2`" in readme
    assert "just scaffold-update" in readme
    assert "check-merge-conflict" in readme


def test_copier_migrations_are_wired() -> None:
    config = COPIER_CONFIG.read_text(encoding="utf-8")

    assert "_migrations: []" in config


def test_default_generation_matches_recorded_output(generated: Path) -> None:
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in generated.rglob("*")
        if path.is_file() and path.name != ".copier-answers.yml"
    )
    for path in files:
        relative = path.relative_to(generated).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")

    assert digest.hexdigest() == EXPECTED_GENERATED_TREE_SHA256


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


def test_explicit_default_toggles_are_byte_identical_to_defaults(tmp_path: Path) -> None:
    implicit = _generate_with_answers(tmp_path / "implicit", {})
    explicit = _generate_with_answers(
        tmp_path / "explicit",
        {"precommit": True, "agents_contract": "full"},
    )

    assert _generated_snapshot(implicit) == _generated_snapshot(explicit)


def test_no_precommit_has_exact_file_delta(tmp_path: Path) -> None:
    baseline = _generated_snapshot(_generate_with_answers(tmp_path / "baseline", {}))
    variant = _generated_snapshot(
        _generate_with_answers(tmp_path / "no-precommit", {"precommit": False})
    )

    assert set(baseline) - set(variant) == {"prek.toml"}
    assert set(variant) - set(baseline) == set()
    assert {
        path for path in set(baseline) & set(variant) if baseline[path] != variant[path]
    } == {".copier-answers.yml", "README.md", "justfile", "pyproject.toml"}
    for path in ("README.md", "justfile", "pyproject.toml"):
        assert b"prek" not in variant[path]
        assert b"pre-push" not in variant[path]


def test_no_agents_md_has_exact_file_delta(tmp_path: Path) -> None:
    baseline = _generated_snapshot(_generate_with_answers(tmp_path / "baseline", {}))
    variant = _generated_snapshot(
        _generate_with_answers(tmp_path / "no-agents-md", {"agents_contract": "none"})
    )

    assert set(baseline) - set(variant) == {"AGENTS.md", "CLAUDE.md"}
    assert set(variant) - set(baseline) == set()
    assert {
        path for path in set(baseline) & set(variant) if baseline[path] != variant[path]
    } == {".copier-answers.yml", "README.md", "docs/README.md"}
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
    assert {
        path for path in baseline if baseline[path] != variant[path]
    } == {".copier-answers.yml", "AGENTS.md"}

    expected_agents = baseline["AGENTS.md"].replace(
        b"3. Green means the unmodified gate exits zero. Then report the behavior changed, tests "
        b"added, architecture impact, and remaining risks.\n\n",
        b"3. Green means the unmodified gate exits zero. Then report the behavior changed, tests "
        b"added, architecture impact, and remaining risks.\n"
        b"4. Commit and push. Publication is complete when the commit and pre-push hooks succeed.\n\n",
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
    stub_dir.mkdir()
    recorded = tmp_path / "gh-args.txt"
    stub = stub_dir / "gh"
    stub.write_text(f'#!/bin/sh\necho "$@" > "{recorded}"\n', encoding="utf-8")
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    return env, recorded


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


def test_init_creates_project_and_git_repository(tmp_path: Path) -> None:
    result = run_cli("init", PROJECT_NAME, str(tmp_path), "--no-github")
    assert result.returncode == 0, result.stdout + result.stderr
    target = tmp_path / PROJECT_NAME
    assert (target / "src" / PACKAGE_NAME).is_dir(), "package name was not derived"
    assert f"Created {PROJECT_NAME}" in result.stdout
    assert (target / ".git").is_dir(), "git repository was not initialized"
    head = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=target,
        env=instantiate.environment_without_local_git_context(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert head.returncode == 0 and head.stdout.count("\n") == 1, "expected one initial commit"


def test_init_honors_explicit_package_name(tmp_path: Path) -> None:
    result = run_cli(
        "init", PROJECT_NAME, str(tmp_path), "--package", "customcore", "--no-git"
    )
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
    result = run_cli("init", PROJECT_NAME, str(tmp_path / "work"), "--public", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--public" in recorded.read_text(encoding="utf-8").split()
    assert "--private" not in recorded.read_text(encoding="utf-8").split()


def test_init_failing_gh_reports_manual_command_and_exit_1(tmp_path: Path) -> None:
    env, _ = make_gh_stub(tmp_path)
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

    assert find_unrendered_jinja(tmp_path) == [
        "missed.txt.jinja: stray .jinja template suffix"
    ]


def test_unrendered_scan_detects_jinja_whitespace_control(tmp_path: Path) -> None:
    (tmp_path / "missed.txt").write_text(
        "{{- package }}\n{%- if package %}\n", encoding="utf-8"
    )

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
    assert artifacts == [], (
        "Cache artifacts leaked into the generated repository:\n"
        + "\n".join(str(path) for path in artifacts)
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
    subprocess.run(
        ["git", "tag", "v0.1.0"], cwd=pack_copy, env=git_env, check=True
    )
    (pack_copy / "template" / "current-worktree.txt").write_text(
        "current\n", encoding="utf-8"
    )
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
    (linked / "template" / "dirty-linked-worktree.txt").write_text(
        dirty_marker, encoding="utf-8"
    )

    before = snapshot_working_tree(primary)
    assert subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=primary,
        env=git_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout == ""

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
    assert subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=primary,
        env=git_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout == ""
    assert (output / "linked-worktree.txt").read_text(encoding="utf-8") == marker
    assert (output / "dirty-linked-worktree.txt").read_text(
        encoding="utf-8"
    ) == dirty_marker


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
    """The guard is stdlib-only, so it must run in the generated repo as-is."""
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


def run_diagram_sync(repo: Path, mode: str) -> subprocess.CompletedProcess[str]:
    """Run the diagram sync script inside a generated repository (pure Python, no Bun)."""
    return subprocess.run(
        [sys.executable, "-m", "scripts.sync_architecture_diagrams", mode],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


GENERATED_DIAGRAM_FILES = (
    "docs/architecture/likec4/generated/model.c4",
    "docs/architecture/likec4/generated/baseline-views.c4",
)


def test_diagram_sync_check_passes_on_fresh_repository(generated: Path) -> None:
    """The committed derived model must match the import graph byte for byte."""
    result = run_diagram_sync(generated, "--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_diagram_sync_detects_drift_and_names_the_fix(tmp_path: Path) -> None:
    output = tmp_path / "repo"
    assert run_instantiate(PROJECT_NAME, PACKAGE_NAME, output).returncode == 0

    planted = output / "src" / PACKAGE_NAME / "domain" / "planted_policy.py"
    planted.write_text('"""Planted module for drift detection."""\n', encoding="utf-8")

    drifted = run_diagram_sync(output, "--check")
    assert drifted.returncode == 1, drifted.stdout + drifted.stderr
    assert "just check" in drifted.stdout + drifted.stderr

    written = run_diagram_sync(output, "--write")
    assert written.returncode == 0, written.stdout + written.stderr
    resynced = run_diagram_sync(output, "--check")
    assert resynced.returncode == 0, resynced.stdout + resynced.stderr


def test_diagram_sync_output_is_byte_stable(tmp_path: Path) -> None:
    output = tmp_path / "repo"
    assert run_instantiate(PROJECT_NAME, PACKAGE_NAME, output).returncode == 0

    assert run_diagram_sync(output, "--write").returncode == 0
    first = [(output / name).read_bytes() for name in GENERATED_DIAGRAM_FILES]
    assert run_diagram_sync(output, "--write").returncode == 0
    second = [(output / name).read_bytes() for name in GENERATED_DIAGRAM_FILES]
    assert first == second


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
        [sys.executable, "-c", program],
        cwd=generated,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "slice ok" in result.stdout
