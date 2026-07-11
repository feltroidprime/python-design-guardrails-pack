"""Tests for instantiate.py, the template generator.

These tests exercise the generator only. The full downstream quality gate is
covered by scripts/validate_pack.py (run through 'just validate').
"""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from instantiate import PACKAGE_TOKEN  # noqa: E402
from validate_pack import find_forbidden_artifacts, find_placeholder_occurrences  # noqa: E402

INSTANTIATE = REPO_ROOT / "instantiate.py"
TEMPLATE = REPO_ROOT / "template"

PROJECT_NAME = "acme-orders"
PACKAGE_NAME = "acme_orders"

EXPECTED_FILES = (
    ".github/workflows/quality.yml",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".python-version",
    "AGENTS.md",
    "README.md",
    "architecture.toml",
    "docs/adr/0000-template.md",
    "docs/architecture/EXCEPTIONS.md",
    "justfile",
    "pyproject.toml",
    "scripts/architecture_guard.py",
    "scripts/architecture_rules.py",
    "scripts/quality_gate.py",
    f"src/{PACKAGE_NAME}/bootstrap.py",
    f"src/{PACKAGE_NAME}/domain/value_objects.py",
    f"src/{PACKAGE_NAME}/py.typed",
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


def test_generated_vertical_slice_executes(generated: Path) -> None:
    """The example slice must be importable and behave under the new package name."""
    program = (
        "import sys\n"
        "sys.path.insert(0, 'src')\n"
        f"from {PACKAGE_NAME}.adapters.inbound.cli import create_item_from_text\n"
        f"from {PACKAGE_NAME}.bootstrap import create_item_handler\n"
        "event = create_item_from_text(create_item_handler(), '  Pack check  ')\n"
        "assert event.name.value == 'Pack check', event.name.value\n"
        "assert event.item_id.value\n"
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
