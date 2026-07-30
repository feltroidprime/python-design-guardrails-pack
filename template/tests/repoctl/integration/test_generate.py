"""Integration evidence for declaration-derived index regeneration."""

import ast
from hashlib import sha256
import inspect
import json
from pathlib import Path
import re
from typing import cast

import pytest

from repoctl.modules.repository_generation.api import (
    DerivedIndexRenderingError,
    LocalRepository,
    MemoryRepository,
    OwnershipZone,
    RepositoryPathCandidate,
    RepositoryPortError,
    classify_path,
    compile_derived_indexes,
)
from tests.repoctl.integration.generation_support import (
    GENERATED_TARGETS,
    generate_indexes,
    generated_bytes,
    write_declaration,
)


def _generated_paths(root: Path) -> tuple[Path, ...]:
    return (
        root / "src" / "acme" / "_generated" / "active_capabilities.py",
        root / "src" / "acme" / "_generated" / "composition.py",
        root / "src" / "acme" / "_generated" / "cli_catalog.py",
        root / "proof" / "_generated" / "index.json",
    )


def _full_tree_digest(root: Path) -> str:
    digest = sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        _ = digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        _ = digest.update(b"\0")
        _ = digest.update(path.read_bytes())
        _ = digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def test_generate_renders_empty_indexes_in_the_derived_zone_only(tmp_path: Path) -> None:
    repository = LocalRepository(root=tmp_path)

    _ = generate_indexes(repository)

    active_path, composition_path, cli_path, proof_path = _generated_paths(tmp_path)
    python_indexes = tuple(
        path.read_text(encoding="utf-8") for path in _generated_paths(tmp_path)[:3]
    )
    proof = cast("dict[str, object]", json.loads(proof_path.read_text(encoding="utf-8")))
    headers = tuple(
        re.search(r"^# source-state-sha256: ([0-9a-f]{64})$", text, re.MULTILINE)
        for text in python_indexes
    )

    assert all(path.is_file() for path in (active_path, composition_path, cli_path, proof_path))
    assert active_path.read_text(encoding="utf-8").endswith(
        "ACTIVE_CAPABILITIES: tuple[str, ...] = ()\n"
    )
    assert composition_path.read_text(encoding="utf-8").endswith(
        "COMPOSITION: tuple[object, ...] = ()\n"
    )
    assert cli_path.read_text(encoding="utf-8").endswith("CLI_CATALOGS: tuple[object, ...] = ()\n")
    assert all(
        "Generated from repository declarations. DO NOT EDIT." in text for text in python_indexes
    )
    assert all(header is not None for header in headers)
    source_digests = {header.group(1) for header in headers if header is not None}
    assert proof["catalogs"] == []
    assert proof["_generated"] == "Generated from repository declarations. DO NOT EDIT."
    assert proof["source_state_sha256"] in source_digests
    assert len(source_digests) == 1
    assert all(
        classify_path(
            RepositoryPathCandidate(value=path.relative_to(tmp_path).as_posix()),
            repository.snapshot().ownership_zones,
        )
        == OwnershipZone("DERIVED")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )


def test_repeated_generation_leaves_the_full_repository_tree_byte_identical(tmp_path: Path) -> None:
    repository = LocalRepository(root=tmp_path)

    _ = generate_indexes(repository)
    first_tree_digest = _full_tree_digest(tmp_path)
    repeated = generate_indexes(repository)

    assert repeated.written_targets == ()
    assert _full_tree_digest(tmp_path) == first_tree_digest


def test_generation_contains_exactly_the_active_capability_in_every_index(tmp_path: Path) -> None:
    repository = LocalRepository(root=tmp_path)
    write_declaration(repository, name="alpha", status="active")
    write_declaration(repository, name="beta", status="retired")

    _ = generate_indexes(repository)

    active_path, composition_path, cli_path, proof_path = _generated_paths(tmp_path)
    active = active_path.read_text(encoding="utf-8")
    composition = composition_path.read_text(encoding="utf-8")
    cli = cli_path.read_text(encoding="utf-8")
    proof = cast("dict[str, object]", json.loads(proof_path.read_text(encoding="utf-8")))

    assert active.count('"acme.modules.alpha"') == 1
    assert "beta" not in active
    assert "from acme.modules.alpha.bootstrap import build as build_alpha" in composition
    assert composition.count("build_alpha,") == 1
    assert "beta" not in composition
    assert (
        "from acme.modules.alpha.adapters.inbound.cli_catalog import COMMANDS as commands_alpha"
        in cli
    )
    assert cli.count("commands_alpha,") == 1
    assert "beta" not in cli
    assert proof["catalogs"] == [{"path": "proof/modules/alpha.toml", "ownership_zone": "product"}]


def test_generation_preserves_system_and_product_proof_catalog_ownership(
    tmp_path: Path,
) -> None:
    repository = LocalRepository(root=tmp_path)
    write_declaration(
        repository,
        name="repository_generation",
        status="active",
        python_module="repoctl.modules.repository_generation",
        proof_catalog="proof/repoctl/repository-generation.toml",
        factory="",
        cli_catalog="",
    )
    write_declaration(repository, name="alpha", status="active")

    _ = generate_indexes(repository)

    proof = cast(
        "dict[str, object]",
        json.loads(_generated_paths(tmp_path)[3].read_text(encoding="utf-8")),
    )

    assert proof["catalogs"] == [
        {"path": "proof/modules/alpha.toml", "ownership_zone": "product"},
        {
            "path": "proof/repoctl/repository-generation.toml",
            "ownership_zone": "foundation",
        },
    ]


@pytest.mark.parametrize(
    ("schema_version", "python_module", "factory", "cli_catalog", "error"),
    [
        pytest.param(2, None, None, None, RepositoryPortError, id="unsupported-schema"),
        pytest.param(1, "evil.outside", "", "", DerivedIndexRenderingError, id="foreign-module"),
        pytest.param(
            1,
            "repoctl.modules.repository_generation",
            "",
            "",
            DerivedIndexRenderingError,
            id="wrong-system-name",
        ),
        pytest.param(1, None, "os:system", "", DerivedIndexRenderingError, id="foreign-factory"),
        pytest.param(
            1,
            None,
            "",
            "subprocess:run",
            DerivedIndexRenderingError,
            id="foreign-cli-catalog",
        ),
    ],
)
def test_invalid_declarations_leave_all_derived_indexes_unwritten(
    schema_version: int,
    python_module: str | None,
    factory: str | None,
    cli_catalog: str | None,
    error: type[Exception],
) -> None:
    repository = MemoryRepository()
    write_declaration(
        repository,
        name="alpha",
        status="active",
        schema_version=schema_version,
        python_module=python_module,
        factory=factory,
        cli_catalog=cli_catalog,
    )

    with pytest.raises(error):
        _ = generate_indexes(repository)

    assert generated_bytes(repository) == dict.fromkeys(GENERATED_TARGETS)


def test_compilation_module_cannot_perform_runtime_module_discovery() -> None:
    source_path = inspect.getsourcefile(compile_derived_indexes)
    assert source_path is not None
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    imported = {
        module
        for node in ast.walk(tree)
        for module in (
            tuple(alias.name for alias in node.names)
            if isinstance(node, ast.Import)
            else ((node.module or ""),)
            if isinstance(node, ast.ImportFrom)
            else ()
        )
    }
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }

    assert all(
        module != forbidden and not module.startswith(f"{forbidden}.")
        for module in imported
        for forbidden in ("importlib", "pkgutil")
    )
    assert "__import__" not in called
