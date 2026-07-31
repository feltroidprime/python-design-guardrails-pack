"""Recursive acceptance for a pure library capability."""

import ast
from pathlib import Path
from typing import cast

import pytest

from tests.recursive.harness import (
    ALPHA,
    PACKAGE,
    REPOCTL_PREFIX,
    prepare_active_shape,
)
from tests.recursive.shape_support import (
    assert_success,
    install_assets,
    json_object,
    run_detached,
    select_capability,
)

pytestmark = pytest.mark.repository_gate

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "shapes" / "pure_library"
PROPERTY_ID = "ALPHA::PAIR-IS-ORDERED"
IMPLEMENTATION_ASSETS = (
    ("api.py.fixture", "src/{package}/modules/{capability}/api.py"),
    (
        "pairs.py.fixture",
        "src/{package}/modules/{capability}/domain/pairs.py",
    ),
    (
        "specifications.py.fixture",
        "src/{package}/modules/{capability}/domain/specifications.py",
    ),
)
EVIDENCE_ASSETS = (
    ("proof.toml.fixture", "proof/modules/{capability}.toml"),
    (
        "proof_test.py.fixture",
        "verification/modules/{capability}/test_ordered_pair_property.py",
    ),
)


class PureLibraryFixture:
    """Install one proof-carrying pure function through the recursive seam."""

    property_id = PROPERTY_ID

    def install_implementation(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None:
        install_assets(
            repository,
            FIXTURE_ROOT,
            package,
            capability,
            PROPERTY_ID,
            IMPLEMENTATION_ASSETS,
        )

    def install_evidence(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None:
        install_assets(
            repository,
            FIXTURE_ROOT,
            package,
            capability,
            PROPERTY_ID,
            EVIDENCE_ASSETS,
        )


def _external_capability_imports(
    repository: Path,
    package: str,
    capability: str,
) -> set[str]:
    module = f"{package}.modules.{capability}"
    capability_root = repository / "src" / package / "modules" / capability
    imports: set[str] = set()
    command = ("git", "ls-files", "-z", "--", "*.py")
    tracked = run_detached(repository, command)
    assert_success(tracked, command)
    for relative in tracked.stdout.split("\0"):
        if not relative:
            continue
        source = repository / relative
        if source.is_relative_to(capability_root):
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and (node.module == module or node.module.startswith(f"{module}."))
        )
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name == module or alias.name.startswith(f"{module}.")
        )
    return imports


def test_pure_library_exposes_only_an_analysed_api(
    tmp_path: Path,
) -> None:
    repository = prepare_active_shape(
        tmp_path / "recursive-project",
        PureLibraryFixture(),
    )
    capability_root = repository / "src" / PACKAGE / "modules" / ALPHA

    assert not (repository / "tests" / "fixtures" / "shapes").exists()
    assert {
        path.relative_to(capability_root).as_posix()
        for path in (capability_root / "application").rglob("*.py")
    } == {"application/__init__.py"}
    assert {
        path.relative_to(capability_root).as_posix()
        for path in (capability_root / "adapters").rglob("*.py")
    } == {
        "adapters/__init__.py",
        "adapters/inbound/__init__.py",
        "adapters/outbound/__init__.py",
    }

    observed = run_detached(
        repository,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    assert_success(
        observed,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    declaration = select_capability(json_object(observed.stdout), ALPHA)
    assert declaration["status"] == "active"
    boundaries = declaration["boundaries"]
    assert isinstance(boundaries, dict)
    assert cast("dict[str, object]", boundaries) == {"inbound": [], "outbound": []}
    assert _external_capability_imports(repository, PACKAGE, ALPHA) == {
        f"{PACKAGE}.modules.{ALPHA}.api"
    }

    command = (
        "uv",
        "run",
        "python",
        "-m",
        "scripts.crosshair_gate",
        "fast",
    )
    analysed = run_detached(repository, command)
    assert_success(analysed, command)
    assert (
        f"{PROPERTY_ID} | {PACKAGE}.modules.{ALPHA}.domain.pairs:ordered_pair |" in analysed.stdout
    )
