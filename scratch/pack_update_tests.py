"""A real Copier update must never rewrite seeded product bytes."""

import errno
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import tomllib
from typing import cast
from unittest.mock import patch

from copier import _main as copier_main, run_copy, run_update
import pytest

import instantiate

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COPIER_CONFIG = REPOSITORY_ROOT / "copier.yml"
TEMPLATE = REPOSITORY_ROOT / "template"
PROJECT_NAME = "preservation-project"
PACKAGE = "preservation_project"
CAPABILITY_NAME = "billing"
FOUNDATION_A = "v1.0.0"
FOUNDATION_B = "v1.0.1"
OVERWRITE_MUTANT = "v1.0.2"
FOUNDATION_B_MARKER = "Foundation version B."
INITIAL_SOURCE_DIGEST = "4fea77788e9666e6b12698b9b4fac85af160db00472e83339460edfddc9f152e"
DERIVED_TEMPLATE_PATHS = (
    Path("src/{{ package }}/_generated/active_capabilities.py"),
    Path("src/{{ package }}/_generated/composition.py"),
    Path("src/{{ package }}/_generated/cli_catalog.py"),
    Path("proof/_generated/index.json"),
)
MUTATED_PRODUCT_PATH = Path(f"src/{PACKAGE}/modules/{CAPABILITY_NAME}/api.py")
COPIER_CLEANUP_ATTEMPTS = 3
COPIER_CLEANUP_RETRY_SECONDS = 0.01


class RetryingTemporaryDirectory(TemporaryDirectory):
    """Retry Copier cleanup when the filesystem transiently reports ENOTEMPTY."""

    def cleanup(self) -> None:
        for attempt in range(COPIER_CLEANUP_ATTEMPTS):
            try:
                super().cleanup()
            except OSError as error:
                if error.errno != errno.ENOTEMPTY or attempt == COPIER_CLEANUP_ATTEMPTS - 1:
                    raise
                time.sleep(COPIER_CLEANUP_RETRY_SECONDS)
            else:
                return


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = instantiate.environment_without_local_git_context()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    source_root = cwd / "src"
    if source_root.is_dir():
        environment["PYTHONPATH"] = str(source_root)
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def commit_all(repository: Path, message: str) -> None:
    staged = run(["git", "add", "--all"], repository)
    assert staged.returncode == 0, staged.stderr
    committed = run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            f"--message={message}",
        ],
        repository,
    )
    assert committed.returncode == 0, committed.stdout + committed.stderr


def tag(repository: Path, version: str) -> None:
    tagged = run(["git", "tag", version], repository)
    assert tagged.returncode == 0, tagged.stderr


def test_retrying_temporary_directory_retries_transient_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_cleanup = TemporaryDirectory.cleanup
    cleanup_attempts = 0

    def flaky_cleanup(directory: TemporaryDirectory) -> None:
        nonlocal cleanup_attempts
        cleanup_attempts += 1
        if cleanup_attempts == 1:
            raise OSError(errno.ENOTEMPTY, "Directory not empty")
        original_cleanup(directory)

    monkeypatch.setattr(TemporaryDirectory, "cleanup", flaky_cleanup)
    directory = RetryingTemporaryDirectory(dir=tmp_path)

    directory.cleanup()

    assert cleanup_attempts == 2


def test_retrying_temporary_directory_preserves_non_transient_cleanup_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_cleanup = TemporaryDirectory.cleanup

    def inaccessible_cleanup(_directory: TemporaryDirectory) -> None:
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(TemporaryDirectory, "cleanup", inaccessible_cleanup)
    directory = RetryingTemporaryDirectory(dir=tmp_path)

    try:
        with pytest.raises(OSError, match="Permission denied"):
            directory.cleanup()
    finally:
        original_cleanup(directory)


def test_update_scenario_no_longer_references_the_hand_seeded_fixture() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    legacy_path = Path("tests", "fixtures", "capability_seed").as_posix()
    legacy_symbol = "CAPABILITY" + "_SEED"

    assert legacy_path not in source
    assert legacy_symbol not in source


def prepare_template(root: Path) -> Path:
    root.mkdir()
    shutil.copy2(COPIER_CONFIG, root / "copier.yml")
    shutil.copytree(TEMPLATE, root / "template")
    initialized = run(["git", "init", "--quiet", "--initial-branch=main"], root)
    assert initialized.returncode == 0, initialized.stderr
    commit_all(root, "Foundation A")
    tag(root, FOUNDATION_A)
    return root


def generate_project(template: Path, project: Path) -> None:
    with instantiate.without_local_git_context():
        run_copy(
            str(template),
            project,
            data={"project_name": PROJECT_NAME, "package": PACKAGE},
            vcs_ref=FOUNDATION_A,
            defaults=True,
            quiet=True,
            skip_tasks=True,
        )
    initialized = run(["git", "init", "--quiet", "--initial-branch=main"], project)
    assert initialized.returncode == 0, initialized.stderr
    commit_all(project, "Render foundation A")


def create_and_customize_product(project: Path) -> tuple[Path, ...]:
    plan_reference = Path(".repo/plans") / f"{CAPABILITY_NAME}.json"
    planned = run(
        [
            sys.executable,
            "-m",
            "repoctl",
            "capability",
            "plan",
            CAPABILITY_NAME,
            "--output",
            str(plan_reference),
        ],
        project,
    )
    assert planned.returncode == 0, planned.stdout + planned.stderr
    applied = run(
        [
            sys.executable,
            "-m",
            "repoctl",
            "capability",
            "apply",
            str(plan_reference),
        ],
        project,
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr

    operations = cast(
        "list[dict[str, str]]",
        json.loads((project / plan_reference).read_text(encoding="utf-8"))["operations"],
    )
    product_paths = tuple(
        Path(operation["path"])
        for operation in operations
        if operation["kind"] == "create_product_seed"
    )
    assert product_paths
    for relative in product_paths:
        path = project / relative
        path.write_bytes(b"# user-owned customization\n" + path.read_bytes())
    commit_all(project, "Create and customize product capability")
    return product_paths


def file_hashes(root: Path, paths: tuple[Path, ...]) -> dict[Path, str]:
    return {path: sha256((root / path).read_bytes()).hexdigest() for path in paths}


def overwritten_paths(
    before: dict[Path, str],
    root: Path,
) -> tuple[Path, ...]:
    return tuple(
        path
        for path, expected in before.items()
        if sha256((root / path).read_bytes()).hexdigest() != expected
    )


def declaration_source_digest(project: Path) -> str:
    declaration = cast(
        "dict[str, object]",
        tomllib.loads((project / ".repo/repository.toml").read_text(encoding="utf-8")),
    )
    derived = cast("dict[str, object]", declaration["derived"])
    source_glob = cast("str", derived["source_glob"])
    digest = sha256()
    for source in sorted(project.glob(source_glob)):
        digest.update(source.relative_to(project).as_posix().encode())
        digest.update(b"\0")
        digest.update(source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def publish_foundation_b(template: Path, project: Path) -> None:
    readme = template / "template/README.md.jinja"
    readme.write_text(
        readme.read_text(encoding="utf-8") + f"\n{FOUNDATION_B_MARKER}\n",
        encoding="utf-8",
    )
    digest = declaration_source_digest(project)
    assert digest != INITIAL_SOURCE_DIGEST
    for relative in DERIVED_TEMPLATE_PATHS:
        path = template / "template" / relative
        content = path.read_text(encoding="utf-8")
        updated = content.replace(INITIAL_SOURCE_DIGEST, digest)
        assert updated != content
        path.write_text(updated, encoding="utf-8")
    commit_all(template, "Foundation B regenerates derived indexes")
    tag(template, FOUNDATION_B)


def publish_overwrite_mutant(template: Path) -> None:
    source = template / "template/src/{{ package }}/modules/billing/api.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('"""Synthetic product-overwrite mutant."""\n', encoding="utf-8")
    commit_all(template, "Mutant writes a product path")
    tag(template, OVERWRITE_MUTANT)


def update_project(project: Path, version: str) -> None:
    with patch.object(copier_main, "TemporaryDirectory", RetryingTemporaryDirectory):
        with instantiate.without_local_git_context():
            run_update(
                project,
                vcs_ref=version,
                defaults=True,
                quiet=True,
                overwrite=True,
                conflict="inline",
                skip_tasks=True,
            )


def test_foundation_update_preserves_every_seeded_product_byte(tmp_path: Path) -> None:
    template = prepare_template(tmp_path / "template-source")
    project = tmp_path / "project"
    generate_project(template, project)
    product_paths = create_and_customize_product(project)
    product_before = file_hashes(project, product_paths)

    mutant_project = tmp_path / "mutant-project"
    cloned = run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(project), str(mutant_project)], tmp_path
    )
    assert cloned.returncode == 0, cloned.stderr

    publish_foundation_b(template, project)
    update_project(project, FOUNDATION_B)

    assert overwritten_paths(product_before, project) == ()
    assert FOUNDATION_B_MARKER in (project / "README.md").read_text(encoding="utf-8")

    publish_overwrite_mutant(template)
    update_project(mutant_project, OVERWRITE_MUTANT)
    assert overwritten_paths(product_before, mutant_project) == (MUTATED_PRODUCT_PATH,)
