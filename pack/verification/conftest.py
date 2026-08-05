"""Bounded Hypothesis profiles and property-ID selection for the proof loop."""

import os
from typing import TYPE_CHECKING, cast

from hypothesis import HealthCheck, settings
import pytest

if TYPE_CHECKING:
    from typing import Protocol

    class _CoverageOptions(Protocol):
        cov_fail_under: int | None
        cov_report: list[str]

    class _CoveragePlugin(Protocol):
        options: _CoverageOptions


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


def _is_verification_only_stateful_run(config: pytest.Config) -> bool:
    """Identify the focused proof loop, which cannot measure product coverage."""
    return (
        cast("str", config.getoption("markexpr")) == "stateful"
        and bool(config.args)
        and all(
            str(argument).replace("\\", "/").startswith("verification/") for argument in config.args
        )
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Keep the full product coverage floor out of verification-only proof loops."""
    if not _is_verification_only_stateful_run(config):
        return
    config.option.cov_fail_under = 0
    config.option.cov_report = []
    coverage_plugin = cast("_CoveragePlugin | None", config.pluginmanager.getplugin("_cov"))
    if coverage_plugin is not None:
        coverage_plugin.options.cov_fail_under = 0
        coverage_plugin.options.cov_report = []


@pytest.hookimpl
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


@pytest.hookimpl
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
