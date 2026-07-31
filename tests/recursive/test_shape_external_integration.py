"""Recursive acceptance for an outbound integration boundary."""

from pathlib import Path
import subprocess
from typing import cast

from tests.recursive.harness import (
    ACTIVATION_EVIDENCE,
    ALPHA,
    REPOCTL_PREFIX,
    run_recursive_walk,
)
from tests.recursive.shape_support import (
    assert_success,
    install_assets,
    json_object,
    run_detached,
    select_capability,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "shapes" / "external_integration"
PROPERTY_ID = "ALPHA::LOOKUP-PRESERVES-KEY"
IMPLEMENTATION_ASSETS = (
    ("api.py.fixture", "src/{package}/modules/{capability}/api.py"),
    (
        "specifications.py.fixture",
        "src/{package}/modules/{capability}/domain/specifications.py",
    ),
    (
        "result.py.fixture",
        "src/{package}/modules/{capability}/domain/result.py",
    ),
    (
        "lookup.py.fixture",
        "src/{package}/modules/{capability}/application/lookup.py",
    ),
    (
        "adapters.py.fixture",
        "src/{package}/modules/{capability}/adapters/outbound/lookup.py",
    ),
)
PROPERTY_EVIDENCE_ASSETS = (
    ("proof.toml.fixture", "proof/modules/{capability}.toml"),
    (
        "proof_test.py.fixture",
        "verification/modules/{capability}/test_lookup_property.py",
    ),
)
PORT_CONTRACT_ASSETS = (
    (
        "contract_test.py.fixture",
        "tests/modules/{capability}/test_lookup_port_contract.py",
    ),
)


class ExternalIntegrationFixture:
    """Install one proof-carrying outbound integration through the recursive seam."""

    property_id = PROPERTY_ID

    def _repoctl(
        self,
        repository: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        return run_detached(repository, (*REPOCTL_PREFIX, *arguments))

    def install_implementation(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None:
        plan = f".repo/plans/{capability}-external-integration.json"
        plan_command = (
            "capability",
            "plan",
            capability,
            "--outbound",
            "transport",
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
        assert isinstance(boundaries, dict)
        assert cast("dict[str, object]", boundaries)["outbound"] == ["transport"]

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
            PROPERTY_EVIDENCE_ASSETS,
        )
        contract = repository / f"tests/modules/{capability}/test_lookup_port_contract.py"
        assert not contract.exists()
        evidence_without_port_contract = tuple(
            flag for flag in ACTIVATION_EVIDENCE if flag != "--port-contract"
        )
        refused = self._repoctl(
            repository,
            "capability",
            "activate",
            capability,
            *evidence_without_port_contract,
        )
        assert refused.returncode == 3
        assert refused.stdout == ""
        failure = json_object(refused.stderr)
        error = failure["error"]
        assert isinstance(error, dict)
        assert cast("dict[str, object]", error)["code"] == "missing_evidence"
        assert "port_contract" in cast("dict[str, object]", error)["message"]

        observed = self._repoctl(repository, "capabilities", "--limit", "100")
        assert_success(observed, (*REPOCTL_PREFIX, "capabilities", "--limit", "100"))
        assert select_capability(json_object(observed.stdout), capability)["status"] == "draft"
        install_assets(
            repository,
            FIXTURE_ROOT,
            package,
            capability,
            PROPERTY_ID,
            PORT_CONTRACT_ASSETS,
        )


def test_external_integration_owns_and_certifies_its_port(
    tmp_path: Path,
) -> None:
    recursive_walk = run_recursive_walk(
        tmp_path / "recursive-project",
        ExternalIntegrationFixture(),
    )

    assert recursive_walk.runtime_capabilities == ("beta",)
    assert "activate alpha" in recursive_walk.steps

    observed = run_detached(
        recursive_walk.repository,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    assert_success(
        observed,
        (*REPOCTL_PREFIX, "capabilities", "--limit", "100"),
    )
    declaration = select_capability(json_object(observed.stdout), ALPHA)
    assert declaration["status"] == "retired"
    assert cast("dict[str, object]", declaration["boundaries"])["outbound"] == ["transport"]
