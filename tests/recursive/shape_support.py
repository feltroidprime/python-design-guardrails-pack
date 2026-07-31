"""Boring process and asset mechanics shared by recursive shape fixtures."""

import json
from pathlib import Path
import subprocess
from typing import cast

import instantiate
from tests.recursive.harness import COMMAND_TIMEOUT_SECONDS

type AssetTargets = tuple[tuple[str, str], ...]


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
