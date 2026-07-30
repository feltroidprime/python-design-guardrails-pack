"""Recursive acceptance for a capability-owned command boundary."""

import json
from pathlib import Path
import subprocess
from typing import cast

import instantiate
from tests.recursive.harness import (
    ACTIVATION_EVIDENCE,
    ALPHA,
    COMMAND_TIMEOUT_SECONDS,
    PACKAGE,
    REPOCTL_PREFIX,
    run_recursive_walk,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "shapes" / "cli_capability"
PROPERTY_ID = "ALPHA::PROBE-READY"
IMPLEMENTATION_ASSETS = (
    ("module_main.py.fixture", "src/{package}/modules/{capability}/__main__.py"),
    ("api.py.fixture", "src/{package}/modules/{capability}/api.py"),
    (
        "probe.py.fixture",
        "src/{package}/modules/{capability}/domain/probe.py",
    ),
    (
        "specifications.py.fixture",
        "src/{package}/modules/{capability}/domain/specifications.py",
    ),
    (
        "cli_catalog.py.fixture",
        "src/{package}/modules/{capability}/adapters/inbound/cli_catalog.py",
    ),
)
EVIDENCE_ASSETS = (
    ("proof.toml.fixture", "proof/modules/{capability}.toml"),
    (
        "proof_test.py.fixture",
        "verification/modules/{capability}/test_probe_property.py",
    ),
)


def _environment(repository: Path) -> dict[str, str]:
    environment = instantiate.environment_without_local_git_context()
    environment.pop("VIRTUAL_ENV", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPYCACHEPREFIX"] = str(repository / ".venv/pycache")
    return environment


def _run(
    repository: Path,
    command: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=repository,
        env=_environment(repository),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )


def _assert_success(
    completed: subprocess.CompletedProcess[str],
    command: tuple[str, ...],
) -> None:
    assert completed.returncode == 0, (
        f"command failed ({completed.returncode}): {' '.join(command)}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )


def _object(raw: str) -> dict[str, object]:
    document = json.loads(raw)
    assert isinstance(document, dict)
    return cast("dict[str, object]", document)


def _capability(document: dict[str, object], name: str) -> dict[str, object]:
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


def _asset_text(asset: str, *, package: str, capability: str) -> str:
    module = f"{package}.modules.{capability}"
    content = (FIXTURE_ROOT / asset).read_text(encoding="utf-8")
    replacements = {
        "@MODULE@": module,
        "@PROPERTY_ID@": PROPERTY_ID,
    }
    for token, value in replacements.items():
        content = content.replace(token, value)
    assert not any(token in content for token in replacements)
    return content


def _install_assets(
    repository: Path,
    package: str,
    capability: str,
    assets: tuple[tuple[str, str], ...],
) -> None:
    for asset, target_template in assets:
        target = repository / target_template.format(package=package, capability=capability)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(
            _asset_text(asset, package=package, capability=capability),
            encoding="utf-8",
        )


class CliCapabilityFixture:
    """Install one proof-carrying CLI capability through the recursive seam."""

    property_id = PROPERTY_ID

    def _repoctl(
        self,
        repository: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        command = (*REPOCTL_PREFIX, *arguments)
        return _run(repository, command)

    def install_implementation(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None:
        plan = f".repo/plans/{capability}-cli.json"
        plan_command = (
            "capability",
            "plan",
            capability,
            "--inbound",
            "cli",
            "--output",
            plan,
        )
        planned = self._repoctl(repository, *plan_command)
        _assert_success(planned, (*REPOCTL_PREFIX, *plan_command))

        apply_command = ("capability", "apply", plan)
        applied = self._repoctl(repository, *apply_command)
        _assert_success(applied, (*REPOCTL_PREFIX, *apply_command))

        observed = self._repoctl(repository, "capabilities", "--limit", "100")
        _assert_success(observed, (*REPOCTL_PREFIX, "capabilities", "--limit", "100"))
        declaration = _capability(_object(observed.stdout), capability)
        boundaries = declaration["boundaries"]
        activation = declaration["activation"]
        assert isinstance(boundaries, dict)
        assert isinstance(activation, dict)
        assert cast("dict[str, object]", boundaries)["inbound"] == ["cli"]
        assert cast("dict[str, object]", activation)["cli_catalog"] == ""

        _install_assets(repository, package, capability, IMPLEMENTATION_ASSETS)

    def install_evidence(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None:
        _install_assets(repository, package, capability, EVIDENCE_ASSETS)
        evidence_without_cli = tuple(
            flag for flag in ACTIVATION_EVIDENCE if flag != "--cli-process-evidence"
        )
        refused = self._repoctl(
            repository,
            "capability",
            "activate",
            capability,
            *evidence_without_cli,
        )
        assert refused.returncode == 3
        assert refused.stdout == ""
        failure = _object(refused.stderr)
        error = failure["error"]
        assert isinstance(error, dict)
        assert cast("dict[str, object]", error)["code"] == "missing_evidence"
        assert "cli_process_evidence" in cast("dict[str, object]", error)["message"]


def test_cli_capability_owns_a_detached_command_boundary(
    tmp_path: Path,
) -> None:
    fixture = CliCapabilityFixture()

    recursive_walk = run_recursive_walk(tmp_path / "recursive-project", fixture)

    assert recursive_walk.runtime_capabilities == ("beta",)
    assert not (recursive_walk.repository / "src" / PACKAGE / "__main__.py").exists()

    command = (
        "uv",
        "run",
        "python",
        "-m",
        f"{PACKAGE}.modules.{ALPHA}",
        "probe",
    )
    completed = _run(recursive_walk.repository, command)
    _assert_success(completed, command)
    assert completed.stderr == ""
    assert _object(completed.stdout) == {
        "command": "probe",
        "data": {"result": "ready"},
        "schema_version": "1.0",
    }

    retired = _run(
        recursive_walk.repository,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    _assert_success(
        retired,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    declaration = _capability(_object(retired.stdout), ALPHA)
    assert declaration["status"] == "retired"
    assert cast("dict[str, object]", declaration["boundaries"])["inbound"] == ["cli"]
    assert cast("dict[str, object]", declaration["activation"])["cli_catalog"] == ""
