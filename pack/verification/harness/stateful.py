"""Typed access to the Hypothesis stateful runner, which ships unannotated."""

from collections.abc import Callable
from typing import cast

from hypothesis import stateful
from hypothesis.stateful import RuleBasedStateMachine

type StateMachineRunner = Callable[[type[RuleBasedStateMachine]], None]

run_state_machine_as_test: StateMachineRunner = cast(
    "StateMachineRunner",
    stateful.run_state_machine_as_test,
)
