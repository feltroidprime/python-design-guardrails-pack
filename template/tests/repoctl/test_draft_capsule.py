import ast
from pathlib import Path
import subprocess
import sys

from scripts.architecture_policy import load_policy
from scripts.architecture_rules import check_source
from scripts.ownership import classify_path
from scripts.ownership_policy import load_ownership_policy

CAPABILITY_ROOT = Path("repoctl/modules/repository_generation")
REQUIRED_SHAPE = (
    Path("api.py"),
    Path("domain"),
    Path("application"),
    Path("adapters/inbound"),
    Path("adapters/outbound"),
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_module(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # ARCH-EXCEPTION: ADR-0007
        [sys.executable, "-m", *arguments],
        cwd=repository_root(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_draft_capsule_has_real_empty_capability_shape() -> None:
    capability = repository_root() / CAPABILITY_ROOT

    assert all((capability / relative).exists() for relative in REQUIRED_SHAPE)
    for source in capability.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        assert ast.get_docstring(tree)
        assert not any(
            isinstance(node, ast.Name) and node.id == "NotImplementedError"
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and ("fake" in node.name.casefold() or "placeholder" in node.name.casefold())
            for node in ast.walk(tree)
        )


def test_draft_capsule_passes_the_shared_capability_validator() -> None:
    result = run_module(
        "scripts.capability_validator",
        "--root",
        CAPABILITY_ROOT.as_posix(),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ownership=FOUNDATION" in result.stdout
    assert "rules=CAP001,CAP002,CAP003" in result.stdout


def test_repoctl_tree_is_entirely_foundation_owned() -> None:
    root = repository_root()
    policy = load_ownership_policy(root)
    repoctl_files = tuple(path for path in (root / "repoctl").rglob("*") if path.is_file())

    assert repoctl_files
    assert {str(classify_path(path.relative_to(root), policy)) for path in repoctl_files} == {
        "FOUNDATION"
    }


def test_repository_generation_application_rejects_ambient_effects() -> None:
    root = repository_root()
    path = root / CAPABILITY_ROOT / "application/__init__.py"
    policy = load_policy(root)
    source = path.read_text(encoding="utf-8")
    clean_codes = {
        item.code
        for item in check_source(
            path,
            source,
            ast.parse(source, filename=str(path)),
            policy,
        )
    }
    assert clean_codes.isdisjoint({"ARCH011", "ARCH012"})
    mutations = (
        source + '\nimport os\n\n\ndef read_state() -> object:\n    return open("state")\n',
        source
        + (
            "\nimport shutil\n\n\ndef copy_state() -> object:\n"
            '    return shutil.copyfile("a", "b")\n'
        ),
    )
    for mutation in mutations:
        mutation_codes = {
            item.code
            for item in check_source(
                path,
                mutation,
                ast.parse(mutation, filename=str(path)),
                policy,
            )
        }
        assert {"ARCH011", "ARCH012"} <= mutation_codes
