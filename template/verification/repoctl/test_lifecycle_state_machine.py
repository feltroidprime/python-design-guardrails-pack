"""Stateful evidence for guarded, non-destructive capability lifecycle changes."""

import dataclasses
import hashlib
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast, final, override

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule
import pytest

from repoctl.modules.repository_generation.api import (
    ActivationEvidence,
    CapabilityIntent,
    LocalRepository,
    MemoryRepository,
    OwnershipRoot,
    OwnershipZone,
    OwnershipZoneRoots,
    RepositoryPathCandidate,
    activate,
    activation_is_closed,
    apply,
    classify_path,
    default_ownership_zones,
    plan,
    retire,
    retirement_is_non_destructive,
)
from verification.harness.assertions import assert_falsifies, assert_property
from verification.harness.stateful import run_state_machine_as_test


def _intent() -> CapabilityIntent:
    return CapabilityIntent(
        schema_version=1,
        name="lifecycle_capability",
        inbound=("python",),
        outbound=(),
    )


def _draft_repository(
    *,
    ownership_zones: tuple[OwnershipZoneRoots, ...] | None = None,
) -> MemoryRepository:
    repository = MemoryRepository(ownership_zones=ownership_zones)
    outcome = apply(plan(repository.snapshot(), _intent()), repository)
    assert outcome.status == "applied"
    return repository


def _active_local_repository(root: Path) -> LocalRepository:
    repository = LocalRepository(root=root)
    outcome = apply(plan(repository.snapshot(), _intent()), repository)
    assert outcome.status == "applied"
    activation = activate("lifecycle_capability", _complete_evidence(), repository)
    assert activation.status == "activated"
    return repository


def _complete_evidence() -> ActivationEvidence:
    return ActivationEvidence(
        architecture_contract=True,
        stable_surface=True,
        normative_property_evidence=True,
        port_contract=True,
        cli_process_evidence=True,
    )


def _declaration_as_product_zones() -> tuple[OwnershipZoneRoots, ...]:
    custom_zones: list[OwnershipZoneRoots] = []
    for zone in default_ownership_zones("acme"):
        if zone.name == OwnershipZone("DECLARATION"):
            roots = (OwnershipRoot(value=".declarations"),)
        elif zone.name == OwnershipZone("PRODUCT"):
            roots = (*zone.roots, OwnershipRoot(value=".repo"))
        else:
            roots = zone.roots
        custom_zones.append(OwnershipZoneRoots(name=zone.name, roots=roots))
    return tuple(custom_zones)


def _status(repository: MemoryRepository | LocalRepository) -> str:
    declaration = next(
        item for item in repository.snapshot().declarations if item.name == "lifecycle_capability"
    )
    return declaration.status


def _product_hashes(repository: LocalRepository) -> tuple[tuple[str, str], ...]:
    snapshot = repository.snapshot()
    hashes: list[tuple[str, str]] = []
    for repository_file in snapshot.files:
        candidate = RepositoryPathCandidate(value=repository_file.path.value)
        if classify_path(candidate, snapshot.ownership_zones) != OwnershipZone("PRODUCT"):
            continue
        content = repository.read_bytes(candidate)
        assert content is not None
        hashes.append((repository_file.path.value, hashlib.sha256(content).hexdigest()))
    return tuple(hashes)


@final
class ActivationClosedMachine(RuleBasedStateMachine):
    """Exercise every incomplete activation checklist through a DRAFT declaration."""

    _repository: MemoryRepository

    def __init__(self) -> None:
        super().__init__()
        self._repository = _draft_repository()

    @rule(
        missing_field=st.sampled_from(
            (
                "architecture_contract",
                "stable_surface",
                "normative_property_evidence",
                "port_contract",
                "cli_process_evidence",
            )
        )
    )
    def refuse_incomplete_activation(self, missing_field: str) -> None:
        evidence = dataclasses.replace(_complete_evidence(), **{missing_field: False})
        outcome = activate("lifecycle_capability", evidence, self._repository)

        assert_property(
            condition=activation_is_closed(
                status=outcome.status,
                missing_evidence=outcome.missing_evidence,
                expected_missing_evidence=(missing_field,),
                declaration_is_draft=_status(self._repository) == "draft",
            ),
            property_id="REPOCTL::ACTIVATION-CLOSED",
        )


@final
class RetirementNonDestructiveMachine(RuleBasedStateMachine):
    """Retire an active capability without changing any PRODUCT bytes."""

    _repository: LocalRepository
    _temporary_directory: TemporaryDirectory[str]

    def __init__(self) -> None:
        super().__init__()
        self._temporary_directory = TemporaryDirectory()
        self._repository = _active_local_repository(Path(self._temporary_directory.name))

    @override
    def teardown(self) -> None:
        self._temporary_directory.cleanup()

    @rule()
    def retire_without_rewriting_product_files(self) -> None:
        if _status(self._repository) != "active":
            return
        before = _product_hashes(self._repository)
        outcome = retire("lifecycle_capability", self._repository)
        after = _product_hashes(self._repository)

        assert_property(
            condition=retirement_is_non_destructive(
                status=outcome.status,
                product_hashes_unchanged=after == before,
                retired_declaration_exists=_status(self._repository) == "retired",
            ),
            property_id="REPOCTL::RETIREMENT-NON-DESTRUCTIVE",
        )


@pytest.mark.proof
@pytest.mark.stateful
@pytest.mark.proves("REPOCTL::ACTIVATION-CLOSED")
def test_activation_requires_current_complete_evidence() -> None:
    run_state_machine_as_test(ActivationClosedMachine)


@pytest.mark.proof
@pytest.mark.stateful
@pytest.mark.proves("REPOCTL::RETIREMENT-NON-DESTRUCTIVE")
def test_retirement_preserves_product_files() -> None:
    run_state_machine_as_test(RetirementNonDestructiveMachine)


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::ACTIVATION-CLOSED")
def test_activation_without_refusal_is_a_real_counterexample() -> None:
    assert_falsifies(
        condition=activation_is_closed(
            status="activated",
            missing_evidence=("architecture_contract",),
            expected_missing_evidence=("architecture_contract",),
            declaration_is_draft=False,
        ),
        property_id="REPOCTL::ACTIVATION-CLOSED",
    )


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::RETIREMENT-NON-DESTRUCTIVE")
def test_changed_product_bytes_are_a_real_retirement_counterexample() -> None:
    assert_falsifies(
        condition=retirement_is_non_destructive(
            status="retired",
            product_hashes_unchanged=False,
            retired_declaration_exists=True,
        ),
        property_id="REPOCTL::RETIREMENT-NON-DESTRUCTIVE",
    )


@pytest.mark.parametrize(
    ("evidence", "missing_evidence"),
    [
        (
            dataclasses.replace(_complete_evidence(), architecture_contract=False),
            ("architecture_contract",),
        ),
        (
            dataclasses.replace(_complete_evidence(), stable_surface=False),
            ("stable_surface",),
        ),
        (
            dataclasses.replace(_complete_evidence(), normative_property_evidence=False),
            ("normative_property_evidence",),
        ),
        (
            dataclasses.replace(_complete_evidence(), port_contract=False),
            ("port_contract",),
        ),
        (
            dataclasses.replace(_complete_evidence(), cli_process_evidence=False),
            ("cli_process_evidence",),
        ),
    ],
)
def test_each_missing_activation_requirement_is_named_in_the_refusal(
    evidence: ActivationEvidence,
    missing_evidence: tuple[str, ...],
) -> None:
    repository = _draft_repository()

    outcome = activate("lifecycle_capability", evidence, repository)

    assert outcome.status == "refused"
    assert outcome.reason == "missing_evidence"
    assert outcome.missing_evidence == missing_evidence
    assert _status(repository) == "draft"


def test_reactivating_a_retired_capability_requires_current_evidence() -> None:
    repository = _draft_repository()
    assert retire("lifecycle_capability", repository).status == "retired"

    refused = activate(
        "lifecycle_capability",
        dataclasses.replace(_complete_evidence(), cli_process_evidence=False),
        repository,
    )
    activated = activate("lifecycle_capability", _complete_evidence(), repository)

    assert refused.status == "refused"
    assert refused.missing_evidence == ("cli_process_evidence",)
    assert _status(repository) == "active"
    assert activated.status == "activated"


def test_transition_refuses_a_declaration_path_owned_as_product() -> None:
    repository = _draft_repository(ownership_zones=_declaration_as_product_zones())
    declaration_path = RepositoryPathCandidate(value=".repo/capabilities/lifecycle_capability.toml")
    before = repository.read_bytes(declaration_path)

    outcome = activate("lifecycle_capability", _complete_evidence(), repository)

    assert outcome.status == "refused"
    assert outcome.reason == "declaration_path_not_owned"
    assert repository.read_bytes(declaration_path) == before
    assert _status(repository) == "draft"


def test_transition_module_exposes_no_delete_or_purge_callable() -> None:
    transition_module = inspect.getmodule(activate)
    assert transition_module is not None
    public_callables = {
        name
        for name, value in cast("dict[str, object]", vars(transition_module)).items()
        if callable(value) and not name.startswith("_")
    }

    assert not {name for name in public_callables if "delete" in name or "purge" in name}
