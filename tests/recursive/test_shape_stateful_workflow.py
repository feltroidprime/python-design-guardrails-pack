"""Recursive acceptance for a stateful workflow capability."""

from pathlib import Path
import subprocess
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

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "shapes" / "stateful_workflow"
PROPERTY_ID = "ALPHA::TERMINAL-RUNS-CLOSE"
IMPLEMENTATION_ASSETS = (
    ("api.py.fixture", "src/{package}/modules/{capability}/api.py"),
    (
        "ports.py.fixture",
        "src/{package}/modules/{capability}/application/ports.py",
    ),
    (
        "workflow.py.fixture",
        "src/{package}/modules/{capability}/application/workflow.py",
    ),
    (
        "entities.py.fixture",
        "src/{package}/modules/{capability}/domain/entities.py",
    ),
    (
        "transitions.py.fixture",
        "src/{package}/modules/{capability}/domain/transitions.py",
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
        "verification/modules/{capability}/test_workflow_state_machine.py",
    ),
)


class StatefulWorkflowFixture:
    """Install one port-driven workflow through the recursive seam."""

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
        plan = f".repo/plans/{capability}-stateful-workflow.json"
        plan_command = (
            "capability",
            "plan",
            capability,
            "--outbound",
            "clock",
            "--outbound",
            "execution",
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
        assert cast("dict[str, object]", boundaries)["outbound"] == ["clock", "execution"]

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


def test_stateful_workflow_closes_terminal_runs_through_injected_ports(
    tmp_path: Path,
) -> None:
    repository = prepare_active_shape(
        tmp_path / "recursive-project",
        StatefulWorkflowFixture(),
    )

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
    assert cast("dict[str, object]", boundaries)["outbound"] == ["clock", "execution"]

    domain_path = repository / "src" / PACKAGE / "modules" / ALPHA / "domain" / "transitions.py"
    original = domain_path.read_bytes()
    mutant = original + b"\nimport time\n\n_AMBIENT_TIME = time.time()\n"
    command = ("uv", "run", "python", "-m", "scripts.architecture_guard")
    try:
        _ = domain_path.write_bytes(mutant)
        guarded = run_detached(repository, command)
    finally:
        _ = domain_path.write_bytes(original)

    assert guarded.returncode == 1
    diagnostic = guarded.stdout + guarded.stderr
    assert domain_path.relative_to(repository).as_posix() in diagnostic
    assert "ARCH011" in diagnostic or "ARCH012" in diagnostic
