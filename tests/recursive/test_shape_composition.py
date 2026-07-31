"""Focused acceptance for composition through the generated factory index."""

import ast
from pathlib import Path
import sys

import instantiate
from tests.recursive.harness import (
    ACTIVATION_EVIDENCE,
    ALPHA,
    BETA,
    PACKAGE,
    PROJECT,
    REPOCTL_PREFIX,
    _assert_product_hashes,
    _product_hashes,
)
from tests.recursive.shape_support import (
    assert_success,
    install_assets,
    json_object,
    run_detached,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "shapes" / "composition"
PROVIDER_ASSET = (("provider_api.py.fixture", "src/{package}/modules/{capability}/api.py"),)
CONSUMER_ASSET = (("consumer_api.py.fixture", "src/{package}/modules/{capability}/api.py"),)
BOOTSTRAP = f"""
import json
import sys

sys.path.insert(0, "src")
from {PACKAGE}._generated.composition import COMPOSITION

provider, consumer = COMPOSITION
print(json.dumps({{
    "modules": [factory.__module__ for factory in COMPOSITION],
    "quote": consumer(provider)(3),
}}))
"""


def _repoctl(repository: Path, *arguments: str) -> None:
    command = (*REPOCTL_PREFIX, *arguments)
    assert_success(run_detached(repository, command), command)


def _imports(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_active_capabilities_compose_only_through_the_generated_index(
    tmp_path: Path,
) -> None:
    repository = tmp_path / PROJECT
    assert instantiate.generate(PROJECT, PACKAGE, repository) is None

    for command in (
        ("git", "init", "--quiet", "--initial-branch=main"),
        ("git", "add", "--all"),
        (
            "git",
            "-c",
            "user.name=composition-tests",
            "-c",
            "user.email=composition-tests@localhost",
            "commit",
            "--quiet",
            "--message=Render N0",
        ),
    ):
        assert_success(run_detached(repository, command), command)

    for capability in (ALPHA, BETA):
        plan = f".repo/plans/{capability}.json"
        _repoctl(repository, "capability", "plan", capability, "--output", plan)
        _repoctl(repository, "capability", "apply", plan)

    install_assets(repository, FIXTURE_ROOT, PACKAGE, ALPHA, "", PROVIDER_ASSET)
    install_assets(repository, FIXTURE_ROOT, PACKAGE, BETA, "", CONSUMER_ASSET)

    factories = {
        ALPHA: f"{PACKAGE}.modules.{ALPHA}.api:unit_price",
        BETA: f"{PACKAGE}.modules.{BETA}.api:build_quote",
    }
    for capability, factory in factories.items():
        declaration = repository / f".repo/capabilities/{capability}.toml"
        source = declaration.read_text(encoding="utf-8")
        assert source.count('factory = ""') == 1
        _ = declaration.write_text(
            source.replace('factory = ""', f'factory = "{factory}"'),
            encoding="utf-8",
        )

    stage = ("git", "add", "--all")
    assert_success(run_detached(repository, stage), stage)
    for capability in (ALPHA, BETA):
        _repoctl(
            repository,
            "capability",
            "activate",
            capability,
            *ACTIVATION_EVIDENCE,
        )
    _repoctl(repository, "generate")

    bootstrap_imports = {
        module for module in _imports(BOOTSTRAP) if module.startswith(f"{PACKAGE}.")
    }
    assert bootstrap_imports == {f"{PACKAGE}._generated.composition"}
    scenario = (sys.executable, "-c", BOOTSTRAP)
    composed = run_detached(repository, scenario)
    assert_success(composed, scenario)
    assert json_object(composed.stdout) == {
        "modules": [
            f"{PACKAGE}.modules.{ALPHA}.api",
            f"{PACKAGE}.modules.{BETA}.api",
        ],
        "quote": 21,
    }

    consumer_root = repository / f"src/{PACKAGE}/modules/{BETA}"
    consumer_api = consumer_root / "api.py"
    provider_module = f"{PACKAGE}.modules.{ALPHA}"
    assert {
        module
        for path in consumer_root.rglob("*.py")
        for module in _imports(path.read_text(encoding="utf-8"))
        if module == provider_module or module.startswith(f"{provider_module}.")
    } == set()
    consumer_hashes = _product_hashes(repository, PACKAGE, BETA)

    original = consumer_api.read_bytes()
    validator = (
        "uv",
        "run",
        "python",
        "-m",
        "scripts.capability_validator",
        "--root",
        f"src/{PACKAGE}/modules/{ALPHA}",
        "--ownership",
        "PRODUCT",
    )
    assert_success(run_detached(repository, validator), validator)
    try:
        _ = consumer_api.write_bytes(
            original + f"\nimport {provider_module}.domain\n".encode(),
        )
        guarded = run_detached(repository, validator)
    finally:
        _ = consumer_api.write_bytes(original)

    assert guarded.returncode == 1
    assert "CAP003" in guarded.stdout + guarded.stderr
    _assert_product_hashes(consumer_hashes, repository, PACKAGE, BETA)

    _repoctl(repository, "capability", "retire", ALPHA)
    _repoctl(repository, "generate")

    _assert_product_hashes(consumer_hashes, repository, PACKAGE, BETA)

    remaining_script = f"""
import json
import sys

sys.path.insert(0, "src")
from {PACKAGE}._generated.composition import COMPOSITION

print(json.dumps({{"modules": [factory.__module__ for factory in COMPOSITION]}}))
"""
    remaining = (sys.executable, "-c", remaining_script)
    imported = run_detached(repository, remaining)
    assert_success(imported, remaining)
    assert json_object(imported.stdout) == {
        "modules": [f"{PACKAGE}.modules.{BETA}.api"],
    }
