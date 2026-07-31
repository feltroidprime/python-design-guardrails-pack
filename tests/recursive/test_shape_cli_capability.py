"""Recursive acceptance for a capability-owned command boundary."""

from pathlib import Path
import subprocess
from typing import cast

import pytest

from tests.recursive.harness import (
    ACTIVATION_EVIDENCE,
    ALPHA,
    PACKAGE,
    REPOCTL_PREFIX,
    prepare_active_shape,
)
from tests.recursive.shape_support import (
    assert_product_hashes,
    assert_success,
    install_assets,
    json_object,
    product_hashes,
    run_detached,
    runtime_capabilities,
    select_capability,
)

pytestmark = pytest.mark.repository_gate

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


class CliCapabilityFixture:
    """Install one proof-carrying CLI capability through the recursive seam."""

    property_id = PROPERTY_ID

    def _repoctl(
        self,
        repository: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        command = (*REPOCTL_PREFIX, *arguments)
        return run_detached(repository, command)

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
        assert_success(planned, (*REPOCTL_PREFIX, *plan_command))

        apply_command = ("capability", "apply", plan)
        applied = self._repoctl(repository, *apply_command)
        assert_success(applied, (*REPOCTL_PREFIX, *apply_command))

        observed = self._repoctl(repository, "capabilities", "--limit", "100")
        assert_success(observed, (*REPOCTL_PREFIX, "capabilities", "--limit", "100"))
        declaration = select_capability(json_object(observed.stdout), capability)
        boundaries = declaration["boundaries"]
        activation = declaration["activation"]
        assert isinstance(boundaries, dict)
        assert isinstance(activation, dict)
        assert cast("dict[str, object]", boundaries)["inbound"] == ["cli"]
        assert cast("dict[str, object]", activation)["cli_catalog"] == ""

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
        failure = json_object(refused.stderr)
        error = failure["error"]
        assert isinstance(error, dict)
        assert cast("dict[str, object]", error)["code"] == "missing_evidence"
        assert "cli_process_evidence" in cast("dict[str, object]", error)["message"]


def test_cli_capability_owns_a_detached_command_boundary(
    tmp_path: Path,
) -> None:
    fixture = CliCapabilityFixture()

    repository = prepare_active_shape(tmp_path / "recursive-project", fixture)

    assert not (repository / "src" / PACKAGE / "__main__.py").exists()
    expected_product_hashes = product_hashes(repository, PACKAGE, ALPHA)

    command = (
        "uv",
        "run",
        "python",
        "-m",
        f"{PACKAGE}.modules.{ALPHA}",
        "probe",
    )
    completed = run_detached(repository, command)
    assert_success(completed, command)
    assert completed.stderr == ""
    expected = {
        "command": "probe",
        "data": {"result": "ready"},
        "schema_version": "1.0",
    }
    assert json_object(completed.stdout) == expected

    active = run_detached(
        repository,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    assert_success(
        active,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    active_declaration = select_capability(json_object(active.stdout), ALPHA)
    assert active_declaration["status"] == "active"
    assert cast("dict[str, object]", active_declaration["boundaries"])["inbound"] == ["cli"]
    assert cast("dict[str, object]", active_declaration["activation"])["cli_catalog"] == ""

    retire = (*REPOCTL_PREFIX, "capability", "retire", ALPHA)
    assert_success(run_detached(repository, retire), retire)
    generate = (*REPOCTL_PREFIX, "generate")
    assert_success(run_detached(repository, generate), generate)

    retired = run_detached(
        repository,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    assert_success(
        retired,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    declaration = select_capability(json_object(retired.stdout), ALPHA)
    assert declaration["status"] == "retired"
    assert cast("dict[str, object]", declaration["boundaries"])["inbound"] == ["cli"]
    assert cast("dict[str, object]", declaration["activation"])["cli_catalog"] == ""
    assert runtime_capabilities(repository, PACKAGE) == ()
    assert_product_hashes(expected_product_hashes, repository, PACKAGE, ALPHA)

    completed_after_retirement = run_detached(repository, command)
    assert_success(completed_after_retirement, command)
    assert completed_after_retirement.stderr == ""
    assert json_object(completed_after_retirement.stdout) == expected
