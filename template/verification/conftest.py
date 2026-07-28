"""Bounded Hypothesis profiles and property-ID selection for the proof loop."""

import os
from typing import cast

from hypothesis import HealthCheck, settings
import pytest

settings.register_profile(
    "fast",
    max_examples=24,
    stateful_step_count=12,
    deadline=None,
    suppress_health_check=(HealthCheck.too_slow,),
)
settings.register_profile(
    "ci",
    max_examples=100,
    stateful_step_count=40,
    deadline=None,
    suppress_health_check=(HealthCheck.too_slow,),
)
settings.register_profile(
    "deep",
    max_examples=750,
    stateful_step_count=150,
    deadline=None,
    suppress_health_check=(HealthCheck.too_slow,),
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Allow the inner loop to execute one stable property ID only."""
    proof_group = parser.getgroup("proof")
    proof_group.addoption(
        "--property-id",
        action="append",
        default=[],
        dest="property_ids",
        metavar="ID",
        help="run only canonical proof and canary tests carrying this property ID",
    )


def _item_property_ids(item: pytest.Item) -> frozenset[str]:
    property_ids: set[str] = set()
    for marker_name in ("proves", "falsifies"):
        for marker in item.iter_markers(marker_name):
            if len(marker.args) == 1 and isinstance(marker.args[0], str):
                property_ids.add(marker.args[0])
    return frozenset(property_ids)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect proof evidence unrelated to explicitly requested property IDs."""
    requested = frozenset(cast("list[str]", config.getoption("property_ids")))
    if not requested:
        return
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        destination = selected if _item_property_ids(item) & requested else deselected
        destination.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
