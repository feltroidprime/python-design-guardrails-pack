"""Independent state-machine evidence for the repository capability protocol."""

import ast
from dataclasses import dataclass
import inspect
from typing import final

from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
import pytest

from repoctl.modules.repository_generation.api import (
    CapabilityIntent,
    CapabilityPlan,
    MemoryRepository,
    Operation,
    RepositoryPath,
    RepositoryPathCandidate,
    apply,
    compile_indexes,
    content_digest as plan_content_digest,
    make_plan,
    plan,
)
from verification.harness import repository_model
from verification.harness.repository_model import PlanFacts, RepositoryFacts, RepositoryModel
from verification.harness.stateful import run_state_machine_as_test

PACKAGE = "acme"


@dataclass(frozen=True, slots=True, kw_only=True)
class _PendingPlan:
    capability_plan: CapabilityPlan
    facts: PlanFacts
    revision: int


def _candidate(path: str) -> RepositoryPathCandidate:
    return RepositoryPathCandidate(value=path)


def _intent(name: str) -> CapabilityIntent:
    return CapabilityIntent(
        schema_version=1,
        name=name,
        inbound=("python",),
        outbound=(),
    )


def _plan_facts(model: RepositoryModel, capability_plan: CapabilityPlan) -> PlanFacts:
    return PlanFacts(
        plan_id=capability_plan.plan_id,
        capability_name=capability_plan.intent.name,
        product_writes=tuple(
            sorted(
                (
                    operation.path.value,
                    repository_model.content_digest(operation.content.encode("utf-8")),
                )
                for operation in capability_plan.operations
                if model.is_product_path(operation.path.value)
            )
        ),
    )


def _facts(repository: MemoryRepository, model: RepositoryModel) -> RepositoryFacts:
    snapshot = repository.snapshot()
    indexes = compile_indexes(snapshot.declarations)
    return RepositoryFacts(
        declarations=tuple(
            sorted(
                (declaration.name, str(declaration.status)) for declaration in snapshot.declarations
            )
        ),
        product_file_hashes=tuple(
            sorted(
                (file.path.value, file.digest)
                for file in snapshot.files
                if model.is_product_path(file.path.value)
            )
        ),
        derived_index_membership=tuple(sorted(entry.name for entry in indexes.active)),
        paths=tuple(sorted(file.path.value for file in snapshot.files)),
    )


def _write_manual_product_file(repository: MemoryRepository, path: str, content: bytes) -> None:
    previous = repository.read_bytes(_candidate(path))
    expected_digest = "absent" if previous is None else repository_model.content_digest(previous)
    repository.write_if_matches(_candidate(path), content, expected_digest=expected_digest)


@final
class RepositoryProtocolMachine(RuleBasedStateMachine):
    """Drive the real port while the primitive-only model judges each transition."""

    _completed_revisions: dict[str, int]
    _manual_change_made: bool
    _model: RepositoryModel
    _pending: dict[str, _PendingPlan]
    _repository: MemoryRepository
    _revision: int

    def __init__(self) -> None:
        super().__init__()
        self._repository = MemoryRepository(package=PACKAGE)
        self._model = RepositoryModel(package=PACKAGE)
        self._pending = {}
        self._completed_revisions = {}
        self._revision = 0
        self._manual_change_made = False
        self._assert_model()

    @rule()
    def plan_capability(self) -> None:
        """Inspect the first capability without changing repository facts."""
        if "alpha" not in self._pending:
            self._pending["alpha"] = self._new_plan("alpha")
        self._assert_model()

    @rule()
    def apply_valid_plan(self) -> None:
        """Apply the fresh first plan when it remains valid."""
        pending = self._pending.get("alpha")
        if pending is None or self._expected_status(pending) != "applied":
            return
        self._apply(pending)

    @rule()
    def apply_same_plan_again(self) -> None:
        """Replay a completed plan while state still matches its completed result."""
        pending = self._pending.get("alpha")
        if (
            pending is None
            or pending.facts.plan_id not in self._model.applied_plan_ids
            or self._completed_revisions.get(pending.facts.plan_id) != self._revision
        ):
            return
        self._apply(pending)

    @rule()
    def plan_stale_capability(self) -> None:
        """Inspect a second plan that can become stale before its first application."""
        if "alpha" not in self._model.declaration_state or "beta" in self._pending:
            return
        self._pending["beta"] = self._new_plan("beta")
        self._assert_model()

    @rule()
    def manually_modify_product_file(self) -> None:
        """Model an ordinary user edit that makes prior plans stale."""
        if "alpha" not in self._model.declaration_state or self._manual_change_made:
            return
        path = f"src/{PACKAGE}/modules/alpha/api.py"
        content = b'"""User-owned alpha public surface."""\n'
        _write_manual_product_file(self._repository, path, content)
        self._model.record_manual_product_write(path, content)
        self._revision += 1
        self._manual_change_made = True
        self._assert_model()

    @rule()
    def apply_stale_plan(self) -> None:
        """Fail closed when the second plan predates a manual product edit."""
        pending = self._pending.get("beta")
        if pending is None or self._expected_status(pending) != "stale_plan":
            return
        self._apply(pending)

    @rule()
    def add_second_capability(self) -> None:
        """Plan and apply a fresh second capability after prior state settles."""
        if "alpha" not in self._model.declaration_state or "gamma" in self._pending:
            return
        pending = self._new_plan("gamma")
        self._pending["gamma"] = pending
        self._apply(pending)

    @rule()
    def regenerate_indexes(self) -> None:
        """Recompute the projection and compare it with declared lifecycle state."""
        self._assert_model()

    @invariant()
    def repository_matches_reference_model(self) -> None:
        """Keep every action history inside the independent protocol model."""
        self._assert_model()

    def _new_plan(self, name: str) -> _PendingPlan:
        capability_plan = plan(self._repository.snapshot(), _intent(name))
        return _PendingPlan(
            capability_plan=capability_plan,
            facts=_plan_facts(self._model, capability_plan),
            revision=self._revision,
        )

    def _expected_status(self, pending: _PendingPlan) -> str:
        return self._model.expected_apply_status(
            pending.facts,
            plan_is_stale=self._plan_is_stale(pending),
        )

    def _apply(self, pending: _PendingPlan) -> None:
        plan_is_stale = self._plan_is_stale(pending)
        outcome = apply(pending.capability_plan, self._repository)
        self._model.record_apply(
            pending.facts,
            status=outcome.status,
            plan_is_stale=plan_is_stale,
        )
        if outcome.status == "applied":
            self._revision += 1
            self._completed_revisions[pending.facts.plan_id] = self._revision
        self._assert_model()

    def _plan_is_stale(self, pending: _PendingPlan) -> bool:
        completed_revision = self._completed_revisions.get(pending.facts.plan_id)
        if completed_revision is not None:
            return completed_revision != self._revision
        return pending.revision != self._revision

    def _assert_model(self) -> None:
        self._model.assert_invariants(_facts(self._repository, self._model))


@final
class ProductOverwriteMutantMachine(RuleBasedStateMachine):
    """A deliberate unsafe apply mutation that the reference model must reject."""

    _facts: PlanFacts | None
    _model: RepositoryModel
    _plan: CapabilityPlan | None
    _repository: MemoryRepository
    steps: list[str]

    def __init__(self) -> None:
        super().__init__()
        self._repository = MemoryRepository(package=PACKAGE)
        self._model = RepositoryModel(package=PACKAGE)
        self._plan = None
        self._facts = None
        self.steps = []
        path = f"src/{PACKAGE}/modules/alpha/api.py"
        content = b'"""Existing user-owned public surface."""\n'
        _write_manual_product_file(self._repository, path, content)
        self._model.record_manual_product_write(path, content)
        self._model.assert_invariants(_facts(self._repository, self._model))

    @rule()
    def plan_capability(self) -> None:
        """Forge the one invalid product-overwrite plan used for mutation detection."""
        if self._plan is not None:
            return
        source = plan(self._repository.snapshot(), _intent("alpha"))
        target = RepositoryPath(value=f"src/{PACKAGE}/modules/alpha/api.py")
        replacement = '"""Mutated repository-control output."""\n'
        self._plan = make_plan(
            generator_version=source.generator_version,
            base_state_digest=source.base_state_digest,
            intent=source.intent,
            operations=(
                Operation(
                    kind="create_product_seed",
                    path=target,
                    precondition=plan_content_digest('"""Existing user-owned public surface."""\n'),
                    content=replacement,
                    content_digest=plan_content_digest(replacement),
                ),
            ),
            result_state_digest=source.result_state_digest,
        )
        self._facts = _plan_facts(self._model, self._plan)
        self.steps.append("plan capability")

    @rule()
    def apply_valid_plan(self) -> None:
        """Perform the intentionally missing product-preservation check."""
        if self._plan is None or self._facts is None:
            return
        operation = self._plan.operations[0]
        self._repository.write_if_matches(
            _candidate(operation.path.value),
            operation.content.encode("utf-8"),
            expected_digest=operation.precondition,
        )
        self.steps.append("apply valid plan")
        try:
            self._model.record_apply(
                self._facts,
                status="applied",
                plan_is_stale=False,
            )
        except AssertionError as error:
            raise AssertionError(
                f"counterexample steps={len(self.steps)} {self.steps!r}: {error}"
            ) from error


@pytest.mark.proof
@pytest.mark.stateful
def test_repository_protocol_state_machine() -> None:
    run_state_machine_as_test(RepositoryProtocolMachine)


def test_product_overwrite_mutation_has_a_short_reported_counterexample() -> None:
    machine = ProductOverwriteMutantMachine()
    machine.plan_capability()

    with pytest.raises(AssertionError, match=r"counterexample steps=2"):
        machine.apply_valid_plan()

    assert machine.steps == ["plan capability", "apply valid plan"]
    assert len(machine.steps) <= 4


def test_reference_model_imports_no_repoctl_application_or_domain_layer() -> None:
    source = inspect.getsource(repository_model)
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert not {
        module_name
        for module_name in imported_modules
        if module_name.startswith(
            (
                "repoctl.modules.repository_generation.application",
                "repoctl.modules.repository_generation.domain",
            )
        )
    }
