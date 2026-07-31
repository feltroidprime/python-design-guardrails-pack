"""One real-command harness for recursive generated-repository scenarios."""

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
from typing import Protocol

import instantiate
from tests.recursive.shape_support import (
    COMMAND_TIMEOUT_SECONDS,
    assert_product_hashes,
    product_hashes,
    runtime_capabilities,
)

PACK_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "recursive_project"
PROJECT = "recursive-project"
ALPHA = "alpha"
BETA = "beta"
REPOCTL_PREFIX = ("uv", "run", "python", "-m", "repoctl")
ACTIVATION_EVIDENCE = (
    "--architecture-contract",
    "--stable-surface",
    "--normative-property-evidence",
    "--port-contract",
    "--cli-process-evidence",
)
INVENTED_BUSINESS_LOGIC = (
    re.compile(r"\bNotImplementedError\b"),
    re.compile(r"(?m)^\s*class\s+\w*(?:Aggregate|Entity|Model|Record)\b"),
    re.compile(r"(?m)^\s*assert\s+(?:True|1(?:\s*==\s*1)?)\b"),
)


class ShapeFixture(Protocol):
    """The sole injection seam: a fixture owns product implementation and evidence writes."""

    property_id: str

    def install_implementation(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None: ...

    def install_evidence(
        self,
        repository: Path,
        package: str,
        capability: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class RecursiveWalkResult:
    """Observable evidence returned by one complete nineteen-step walk."""

    repository: Path
    steps: tuple[str, ...]
    invocations: tuple[tuple[str, ...], ...]
    runtime_capabilities: tuple[str, ...]


@dataclass(slots=True)
class _CommandHarness:
    repository: Path
    invocations: list[tuple[str, ...]] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        working_directory = self.repository if cwd is None else cwd
        self.invocations.append(command)
        environment = instantiate.environment_without_local_git_context()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPYCACHEPREFIX"] = str(self.repository / ".venv/pycache")
        completed = subprocess.run(
            command,
            cwd=working_directory,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0:
            message = (
                f"command failed ({completed.returncode}): {' '.join(command)}\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
            raise AssertionError(message)
        return completed

    def repoctl(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return self.run((*REPOCTL_PREFIX, *arguments))

    def plan_and_apply(self, capability: str) -> None:
        plan = f".repo/plans/{capability}.json"
        _ = self.repoctl("capability", "plan", capability, "--output", plan)
        _ = self.repoctl("capability", "apply", plan)

    def activate(self, capability: str) -> None:
        _ = self.repoctl(
            "capability",
            "activate",
            capability,
            *ACTIVATION_EVIDENCE,
        )
        _ = self.repoctl("generate")

    def retire(self, capability: str) -> None:
        _ = self.repoctl("capability", "retire", capability)
        _ = self.repoctl("generate")

    def stage_all(self) -> None:
        _ = self.run(("git", "add", "--all"))

    def record(self, step: str) -> None:
        self.steps.append(step)


def assert_no_invented_business_logic(capability_root: Path) -> None:
    """Reject placeholder implementations in a freshly CLI-created capsule."""
    sources = tuple(
        path.read_text(encoding="utf-8")
        for path in sorted(capability_root.rglob("*.py"))
        if path.is_file()
    )
    matches = tuple(
        pattern.pattern
        for pattern in INVENTED_BUSINESS_LOGIC
        if any(pattern.search(source) for source in sources)
    )
    assert not matches, f"invented business logic matched: {matches}"


def _render_repository(harness: _CommandHarness) -> None:
    error = instantiate.generate(PROJECT, PACKAGE, harness.repository)
    assert error is None, error
    harness.record("render N0")

    _ = harness.run(("git", "init", "--quiet", "--initial-branch=main"))
    harness.stage_all()
    _ = harness.run(
        (
            "git",
            "-c",
            "user.name=recursive-tests",
            "-c",
            "user.email=recursive-tests@localhost",
            "commit",
            "--quiet",
            "--message=Render N0",
        )
    )


def _render_and_bootstrap(harness: _CommandHarness) -> None:
    _render_repository(harness)
    _ = harness.run(("just", "bootstrap"))
    harness.record("bootstrap N0")


def prepare_active_shape(
    repository: Path,
    fixture: ShapeFixture,
) -> Path:
    """Create, activate, and certify one shape through real CLI commands."""
    harness = _CommandHarness(repository=repository)
    _render_repository(harness)

    harness.plan_and_apply(ALPHA)
    assert_no_invented_business_logic(repository / "src" / PACKAGE / "modules" / ALPHA)
    fixture.install_implementation(repository, PACKAGE, ALPHA)
    fixture.install_evidence(repository, PACKAGE, ALPHA)
    harness.stage_all()
    harness.activate(ALPHA)
    _ = harness.run(("just", "check"))

    assert runtime_capabilities(repository, PACKAGE) == (ALPHA,)
    return repository


def run_recursive_walk(
    repository: Path,
    fixture: ShapeFixture,
) -> RecursiveWalkResult:
    """Execute the specification's nineteen recursive steps in one staged scenario."""
    harness = _CommandHarness(repository=repository)
    _render_and_bootstrap(harness)

    _ = harness.run(
        (
            "uv",
            "run",
            "python",
            "-m",
            "scripts.capability_validator",
            "--root",
            "repoctl/modules/repository_generation",
            "--ownership",
            "FOUNDATION",
        )
    )
    harness.record("validate repository-generation as a system capability")

    _ = harness.repoctl("capabilities")
    harness.record("run repo capabilities")

    plan = f".repo/plans/{ALPHA}.json"
    _ = harness.repoctl("capability", "plan", ALPHA, "--output", plan)
    harness.record("plan capability alpha")
    _ = harness.repoctl("capability", "apply", plan)
    harness.record("apply capability alpha")

    assert_no_invented_business_logic(repository / "src" / PACKAGE / "modules" / ALPHA)
    harness.record("assert alpha contains no invented business logic")

    fixture.install_implementation(repository, PACKAGE, ALPHA)
    harness.record("add a minimal real alpha implementation from a test fixture")
    fixture.install_evidence(repository, PACKAGE, ALPHA)
    harness.stage_all()
    harness.record("add alpha properties and evidence")

    harness.activate(ALPHA)
    harness.record("activate alpha")

    _ = harness.run(("just", "prove-one", fixture.property_id))
    harness.record("run prove-one for alpha")

    _ = harness.run(("just", "check"))
    harness.record("run the full gate")
    alpha_hashes = product_hashes(repository, PACKAGE, ALPHA)

    harness.plan_and_apply(BETA)
    assert_no_invented_business_logic(repository / "src" / PACKAGE / "modules" / BETA)
    harness.record("plan and apply capability beta from the resulting N1 repository")

    assert_product_hashes(alpha_hashes, repository, PACKAGE, ALPHA)
    harness.record("verify alpha's product bytes are unchanged")

    harness.activate(BETA)
    assert_product_hashes(alpha_hashes, repository, PACKAGE, ALPHA)
    harness.record("activate beta")

    harness.retire(ALPHA)
    harness.record("retire alpha")

    assert_product_hashes(alpha_hashes, repository, PACKAGE, ALPHA)
    harness.record("verify alpha's files remain unchanged")

    active = runtime_capabilities(repository, PACKAGE)
    assert active == (BETA,), active
    harness.record("verify derived runtime indexes contain beta but not alpha")

    harness.stage_all()
    _ = harness.run(("just", "check"))
    harness.record("run the full gate again")

    return RecursiveWalkResult(
        repository=repository,
        steps=tuple(harness.steps),
        invocations=tuple(harness.invocations),
        runtime_capabilities=active,
    )
