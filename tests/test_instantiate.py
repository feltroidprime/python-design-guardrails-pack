"""Tests for instantiate.py, the template generator.

These tests exercise the generator only. The full downstream quality gate is
covered by scripts/validate_pack.py (run through 'just validate').
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

# Import paths are provided by tests/conftest.py.
from instantiate import PACKAGE_TOKEN
from validate_pack import find_forbidden_artifacts, find_placeholder_occurrences

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANTIATE = REPO_ROOT / "instantiate.py"
TEMPLATE = REPO_ROOT / "template"

PROJECT_NAME = "acme-orders"
PACKAGE_NAME = "acme_orders"

EXPECTED_FILES = (
    ".github/workflows/quality.yml",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".python-version",
    ".vscode/settings.json",
    "AGENTS.md",
    "README.md",
    "architecture.toml",
    "docs/README.md",
    "docs/adr/0000-template.md",
    "docs/adr/0001-derived-architecture-diagrams.md",
    "docs/adr/0002-foundation-ports-and-reference-adapters.md",
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
    "scripts/docs_guard.py",
    "scripts/none_discipline.py",
    "scripts/quality_gate.py",
    "scripts/sync_architecture_diagrams.py",
    f"src/{PACKAGE_NAME}/__main__.py",
    f"src/{PACKAGE_NAME}/adapters/outbound/sqlite_repository.py",
    f"src/{PACKAGE_NAME}/application/errors.py",
    f"src/{PACKAGE_NAME}/bootstrap.py",
    f"src/{PACKAGE_NAME}/domain/value_objects.py",
    f"src/{PACKAGE_NAME}/py.typed",
    "tests/contract/item_repository_contract.py",
    "tests/unit/domain/test_value_objects.py",
)


def run_instantiate(
    project: str, package: str, output: Path, *, script: Path = INSTANTIATE
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), project, package, str(output)],
        capture_output=True,
        text=True,
        check=False,
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
    assert "uv sync --all-groups" in result.stdout


@pytest.mark.parametrize(
    "project",
    ["My-Product", "-orders", "orders app", "orders/app", ""],
)
def test_invalid_project_names_are_rejected(project: str, tmp_path: Path) -> None:
    result = run_instantiate(project, PACKAGE_NAME, tmp_path / "out")
    assert result.returncode == 2
    assert "Project name" in result.stdout
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "package",
    ["1orders", "acme-orders", "Acme", "acme orders", ""],
)
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


def test_init_creates_project_and_git_repository(tmp_path: Path) -> None:
    result = run_cli("init", PROJECT_NAME, str(tmp_path), "--no-github")
    assert result.returncode == 0, result.stdout + result.stderr
    target = tmp_path / PROJECT_NAME
    assert (target / "src" / PACKAGE_NAME).is_dir(), "package name was not derived"
    assert f"Created {PROJECT_NAME}" in result.stdout
    assert (target / ".git").is_dir(), "git repository was not initialized"
    head = subprocess.run(
        ["git", "log", "--oneline"], cwd=target, capture_output=True, text=True, check=False
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
    assert find_placeholder_occurrences(target) == []


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


def test_package_directory_is_renamed(generated: Path) -> None:
    assert (generated / "src" / PACKAGE_NAME).is_dir()
    assert not (generated / "src" / PACKAGE_TOKEN).exists()


def test_every_placeholder_is_replaced(generated: Path) -> None:
    leftovers = find_placeholder_occurrences(generated)
    assert leftovers == [], "Unreplaced placeholders:\n" + "\n".join(leftovers)


def test_template_itself_contains_no_local_artifacts() -> None:
    artifacts = find_forbidden_artifacts(TEMPLATE)
    assert artifacts == [], (
        "template/ contains local runtime artifacts that would leak into every "
        "generated repository:\n" + "\n".join(str(path) for path in artifacts)
    )


def test_planted_cache_artifacts_never_reach_generated_repository(tmp_path: Path) -> None:
    """Even a dirty template copy must produce a clean repository."""
    pack_copy = tmp_path / "pack"
    pack_copy.mkdir()
    shutil.copy(INSTANTIATE, pack_copy / "instantiate.py")
    shutil.copytree(TEMPLATE, pack_copy / "template")

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
    assert "sync_architecture_diagrams --write" in drifted.stdout + drifted.stderr

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
