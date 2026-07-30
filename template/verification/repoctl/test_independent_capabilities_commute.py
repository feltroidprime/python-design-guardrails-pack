"""Metamorphic evidence that independent capability application order commutes."""

from hashlib import sha256
import json
from typing import final

from hypothesis import assume, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, precondition, rule
import pytest

from repoctl.modules.repository_generation.api import (
    CapabilityIntent,
    MemoryRepository,
    RepositorySnapshot,
    apply,
    plan,
)
from verification.harness.assertions import assert_falsifies, assert_property
from verification.harness.stateful import run_state_machine_as_test
from verification.repoctl.specifications import canonical_states_match

CAPABILITY_NAMES = st.from_regex(
    r"[a-z][a-z0-9]{0,5}(?:_[a-z0-9]{1,5})?",
    fullmatch=True,
)


def _canonical_state_digest(snapshot: RepositorySnapshot) -> str:
    """Hash semantic state after the snapshot excludes plans and journal timestamps."""
    payload = {
        "schema_version": snapshot.schema_version,
        "package": snapshot.package,
        "declarations": sorted(
            (declaration.canonical_payload() for declaration in snapshot.declarations),
            key=lambda declaration: str(declaration["name"]),
        ),
        "files": sorted(
            (
                {"path": repository_file.path.value, "digest": repository_file.digest}
                for repository_file in snapshot.files
            ),
            key=lambda repository_file: repository_file["path"],
        ),
        "ownership": sorted(
            (
                {
                    "zone": str(zone.name),
                    "roots": sorted(root.value for root in zone.roots),
                }
                for zone in snapshot.ownership_zones
            ),
            key=lambda zone: zone["zone"],
        ),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


def _intent(name: str) -> CapabilityIntent:
    return CapabilityIntent(
        schema_version=1,
        name=name,
        inbound=("python",),
        outbound=(),
    )


@final
class IndependentCapabilityOrderMachine(RuleBasedStateMachine):
    """Retain two repositories while advancing opposite application orders."""

    def __init__(self) -> None:
        super().__init__()
        self._forward = MemoryRepository()
        self._reverse = MemoryRepository()
        self._orders = (("", ""), ("", ""))
        self._step = 0

    @initialize(first=CAPABILITY_NAMES, second=CAPABILITY_NAMES)
    def choose_independent_intents(self, first: str, second: str) -> None:
        _ = assume(first != second)
        self._forward = MemoryRepository()
        self._reverse = MemoryRepository()
        self._orders = ((first, second), (second, first))
        self._step = 0

    def _has_pending_intents(self) -> bool:
        return self._step < 2

    @precondition(_has_pending_intents)
    @rule()
    def apply_next_intent_in_each_order(self) -> None:
        forward_outcome = apply(
            plan(
                self._forward.snapshot(),
                _intent(self._orders[0][self._step]),
            ),
            self._forward,
        )
        reverse_outcome = apply(
            plan(
                self._reverse.snapshot(),
                _intent(self._orders[1][self._step]),
            ),
            self._reverse,
        )
        assert forward_outcome.status == reverse_outcome.status == "applied"
        self._step += 1

    def _has_complete_orders(self) -> bool:
        return self._step == 2

    @precondition(_has_complete_orders)
    @rule()
    def verify_commutative_terminal_state(self) -> None:
        assert_property(
            condition=canonical_states_match(
                _canonical_state_digest(self._forward.snapshot()),
                _canonical_state_digest(self._reverse.snapshot()),
            ),
            property_id="REPOCTL::INDEPENDENT-CAPABILITIES-COMMUTE",
        )


@pytest.mark.proof
@pytest.mark.stateful
@pytest.mark.proves("REPOCTL::INDEPENDENT-CAPABILITIES-COMMUTE")
def test_independent_capability_application_orders_commute() -> None:
    run_state_machine_as_test(IndependentCapabilityOrderMachine)


@pytest.mark.proof
@pytest.mark.falsifies("REPOCTL::INDEPENDENT-CAPABILITIES-COMMUTE")
def test_different_state_digests_are_a_real_commutativity_counterexample() -> None:
    assert_falsifies(
        condition=canonical_states_match(
            "sha256:" + "0" * 64,
            "sha256:" + "1" * 64,
        ),
        property_id="REPOCTL::INDEPENDENT-CAPABILITIES-COMMUTE",
    )
