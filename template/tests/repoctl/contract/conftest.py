"""Pytest behavior shared by isolated repository-port contract runs."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Keep a contract-only selection focused on its port behavior."""
    if config.getoption("markexpr") != "contract":
        return

    coverage_plugin = config.pluginmanager.getplugin("_cov")
    if coverage_plugin is not None:
        _ = config.pluginmanager.unregister(coverage_plugin)
