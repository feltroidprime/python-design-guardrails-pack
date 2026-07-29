"""A real Copier update must never rewrite seeded product bytes."""

from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tomllib
from typing import cast

from copier import run_copy, run_update

import instantiate
from scripts.ownership import classify_path
from scripts.ownership_policy import load_ownership_policy

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COPIER_CONFIG = REPOSITORY_ROOT / "copier.yml"
TEMPLATE = REPOSITORY_ROOT / "template"
CAPABILITY_SEED = REPOSITORY_ROOT / "tests/fixtures/capability_seed"
PROJECT_NAME = "preservation-project"
PACKAGE = "preservation_project"
FOUNDATION_A = "v1.0.0"
FOUNDATION_B = "v1.0.1"
OVERWRITE_MUTANT = "v1.0.2"
FOUNDATION_B_MARKER = "Foundation version B."
EMPTY_SOURCE_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
DERIVED_PATHS = (
    Path(f"src/{PACKAGE}/_generated/active_capabilities.py"),
    Path(f"src/{PACKAGE}/_generated/composition.py"),
    Path(f"src/{PACKAGE}/_generated/cli_catalog.py"),
    Path("proof/_generated/index.json"),
)
DERIVED_TEMPLATE_PATHS = (
    Path("src/{{ package }}/_generated/active_capabilities.py"),
    Path("src/{{ package }}/_generated/composition.py"),
    Path("src/{{ package }}/_generated/cli_catalog.py"),
    Path("proof/_generated/index.json"),
)
MUTATED_PRODUCT_PATH = Path(f"src/{PACKAGE}/modules/billing/api.py")


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=instantiate.environment_without_local_git_context(),
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


def mapped_seed_path(relative: Path) -> Path:
    parts = list(relative.parts)
    if parts[:2] == ["src", "seed_package"]:
        parts[1] = PACKAGE
    return Path(*parts)


def seed_and_customize_product(project: Path) -> tuple[Path, ...]:
    seeded: list[Path] = []
    for source in sorted(path for path in CAPABILITY_SEED.rglob("*") if path.is_file()):
        relative = mapped_seed_path(source.relative_to(CAPABILITY_SEED))
        destination = project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes().replace(b"seed_package", PACKAGE.encode()))
        seeded.append(relative)

    policy = load_ownership_policy(project)
    product_paths = tuple(path for path in seeded if str(classify_path(path, policy)) == "PRODUCT")
    assert product_paths
    for relative in product_paths:
        path = project / relative
        path.write_bytes(b"# user-owned customization\n" + path.read_bytes())
    commit_all(project, "Seed and customize product capability")
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
    assert digest != EMPTY_SOURCE_DIGEST
    for relative in DERIVED_TEMPLATE_PATHS:
        path = template / "template" / relative
        content = path.read_text(encoding="utf-8")
        updated = content.replace(EMPTY_SOURCE_DIGEST, digest)
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
    product_paths = seed_and_customize_product(project)
    product_before = file_hashes(project, product_paths)
    derived_before = {path: (project / path).read_bytes() for path in DERIVED_PATHS}

    mutant_project = tmp_path / "mutant-project"
    cloned = run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(project), str(mutant_project)], tmp_path
    )
    assert cloned.returncode == 0, cloned.stderr

    publish_foundation_b(template, project)
    update_project(project, FOUNDATION_B)

    assert overwritten_paths(product_before, project) == ()
    assert FOUNDATION_B_MARKER in (project / "README.md").read_text(encoding="utf-8")
    assert {
        path for path, content in derived_before.items() if (project / path).read_bytes() != content
    } == set(DERIVED_PATHS)

    publish_overwrite_mutant(template)
    update_project(mutant_project, OVERWRITE_MUTANT)
    assert overwritten_paths(product_before, mutant_project) == (MUTATED_PRODUCT_PATH,)
