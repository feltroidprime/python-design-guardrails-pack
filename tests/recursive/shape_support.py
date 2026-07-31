"""Boring process and asset mechanics shared by recursive shape fixtures."""

import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import cast

import instantiate

type AssetTargets = tuple[tuple[str, str], ...]
COMMAND_TIMEOUT_SECONDS = 900


def run_detached(
    repository: Path,
    command: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    """Run one noninteractive command inside a generated repository."""
    environment = instantiate.environment_without_local_git_context()
    environment.pop("VIRTUAL_ENV", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPYCACHEPREFIX"] = str(repository / ".venv/pycache")
    return subprocess.run(
        command,
        cwd=repository,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )


def assert_success(
    completed: subprocess.CompletedProcess[str],
    command: tuple[str, ...],
) -> None:
    """Fail with both process streams when a command is unsuccessful."""
    assert completed.returncode == 0, (
        f"command failed ({completed.returncode}): {' '.join(command)}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )


def json_object(raw: str) -> dict[str, object]:
    """Decode one JSON object from a detached command stream."""
    document = json.loads(raw)
    assert isinstance(document, dict)
    return cast("dict[str, object]", document)


def select_capability(document: dict[str, object], name: str) -> dict[str, object]:
    """Select exactly one named capability from a repoctl response."""
    data = document["data"]
    assert isinstance(data, dict)
    capabilities = cast("dict[str, object]", data)["capabilities"]
    assert isinstance(capabilities, list)
    matches = [
        cast("dict[str, object]", item)
        for item in capabilities
        if isinstance(item, dict) and item.get("name") == name
    ]
    assert len(matches) == 1
    return matches[0]


def product_hashes(repository: Path, package: str, capability: str) -> dict[str, str]:
    """Hash every PRODUCT file owned by one capability."""
    roots = (
        repository / "src" / package / "modules" / capability,
        repository / "tests" / "modules" / capability,
        repository / "verification" / "modules" / capability,
        repository / "docs" / "product" / capability,
    )
    files = {path for root in roots if root.is_dir() for path in root.rglob("*") if path.is_file()}
    proof_catalog = repository / "proof" / "modules" / f"{capability}.toml"
    if proof_catalog.is_file():
        files.add(proof_catalog)
    assert files, f"{capability} has no product files"
    return {
        path.relative_to(repository).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in sorted(files)
    }


def assert_product_hashes(
    expected: dict[str, str],
    repository: Path,
    package: str,
    capability: str,
) -> None:
    """Assert that one capability's complete PRODUCT surface is unchanged."""
    observed = product_hashes(repository, package, capability)
    assert observed == expected, f"{capability} product bytes changed: {observed!r}"


def runtime_capabilities(repository: Path, package: str) -> tuple[str, ...]:
    """Read active capability names from the generated runtime index."""
    index = repository / "src" / package / "_generated" / "active_capabilities.py"
    tree = ast.parse(index.read_text(encoding="utf-8"), filename=str(index))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ACTIVE_CAPABILITIES"
    )
    modules = ast.literal_eval(assignment.value)
    assert isinstance(modules, tuple)
    assert all(isinstance(module, str) for module in modules)
    return tuple(module.rsplit(".", maxsplit=1)[-1] for module in modules)


def install_assets(
    repository: Path,
    fixture_root: Path,
    package: str,
    capability: str,
    property_id: str,
    assets: AssetTargets,
) -> None:
    """Render and install one fixture's declared asset-to-target mapping."""
    replacements = {
        "@MODULE@": f"{package}.modules.{capability}",
        "@PROPERTY_ID@": property_id,
    }
    for asset, target_template in assets:
        content = (fixture_root / asset).read_text(encoding="utf-8")
        for token, value in replacements.items():
            content = content.replace(token, value)
        assert not any(token in content for token in replacements)

        target = repository / target_template.format(package=package, capability=capability)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(content, encoding="utf-8")
