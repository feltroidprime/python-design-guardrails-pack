"""Shared test bootstrap: git-context isolation.

A test that runs `git` inside a directory it created must not reach the
repository that invoked pytest. A git hook exports `GIT_DIR`, `GIT_INDEX_FILE`
and related variables, so a nested `git add` writes to the wrong index. This
fixture removes those variables for the whole session.

`pyproject.toml` puts the repository root and `pack/` on `sys.path`, so every
module imports `scripts.*` and `verification.*` with a plain import.
"""

from collections.abc import Iterator
import os

import pytest

LOCAL_GIT_ENVIRONMENT = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)


def is_local_git_environment(key: str) -> bool:
    """Return whether *key* can bind git commands to a caller's repository."""
    return key in LOCAL_GIT_ENVIRONMENT or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))


def environment_without_local_git_context() -> dict[str, str]:
    """Copy the process environment without a calling repository's git context."""
    return {key: value for key, value in os.environ.items() if not is_local_git_environment(key)}


@pytest.fixture(scope="session", autouse=True)
def isolate_invoking_git_repository() -> Iterator[None]:
    """Keep git commands in tests scoped to the repositories they create."""
    inherited = {
        key: os.environ.pop(key) for key in tuple(os.environ) if is_local_git_environment(key)
    }
    try:
        yield
    finally:
        os.environ.update(inherited)
