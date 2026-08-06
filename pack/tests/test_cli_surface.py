"""Tests for the api-surface rules `CLI001` to `CLI004`.

The rules read the filesystem layout only, so they check every `<cap>/api.py`,
composed or not. Each of the four codes fires on this uncomposed tree too.
"""

from pathlib import Path

import pytest

from scripts.architecture_guard import check_files
from scripts.architecture_policy import Policy, load_policy
from tests.policy_tree import write_policy_tree

API = "src/pkg/alpha/api.py"
HEADER = '"""The alpha capability."""\n'

RENDERABLE = '''

def report(name: str, *, verbose: bool = False) -> str:
    """Report one line."""
    return name
'''

BOOLEAN_DEFAULT = '''

def report(*, public: bool = True) -> str:
    """Report one line."""
    return "ok"
'''


@pytest.fixture
def policy(tmp_path: Path) -> Policy:
    return load_policy(write_policy_tree(tmp_path))


def run_check(policy: Policy, relative: str, source: str) -> list[str]:
    path = policy.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(source, encoding="utf-8")
    return [item.code for item in check_files((path,), policy)]


def test_a_renderable_api_surface_stays_silent(policy: Policy) -> None:
    codes = run_check(policy, API, HEADER + RENDERABLE)
    assert codes == []


def test_cli001_rejects_a_reserved_parameter_name(policy: Policy) -> None:
    codes = run_check(
        policy,
        API,
        HEADER
        + '\n\ndef report(format: str) -> str:\n    """Report one line."""\n    return format\n',
    )
    assert codes == ["CLI001"]


def test_cli002_rejects_a_module_without_a_docstring(policy: Policy) -> None:
    codes = run_check(
        policy,
        API,
        'def report() -> str:\n    """Report one line."""\n    return "ok"\n',
    )
    assert codes == ["CLI002"]


def test_cli002_rejects_a_public_function_without_a_docstring(policy: Policy) -> None:
    codes = run_check(policy, API, HEADER + '\n\ndef report() -> str:\n    return "ok"\n')
    assert codes == ["CLI002"]


def test_cli003_rejects_an_annotation_outside_the_closed_set(policy: Policy) -> None:
    codes = run_check(
        policy,
        API,
        HEADER
        + '\n\ndef report(item: complex) -> str:\n    """Report one line."""\n    return "ok"\n',
    )
    assert codes == ["CLI003"]


def test_cli003_rejects_a_missing_return_annotation(policy: Policy) -> None:
    codes = run_check(
        policy,
        API,
        HEADER + '\n\ndef report(name: str):\n    """Report one line."""\n    return name\n',
    )
    assert codes == ["CLI003"]


def test_cli004_rejects_a_boolean_without_a_false_default(policy: Policy) -> None:
    codes = run_check(policy, API, HEADER + BOOLEAN_DEFAULT)
    assert codes == ["CLI004"]


def test_the_rules_ignore_a_module_that_is_not_a_capability_api(policy: Policy) -> None:
    codes = run_check(policy, "src/pkg/alpha/domain/entities.py", "def build(): return 1\n")
    assert codes == []


def test_the_rules_ignore_the_pack_owned_foundation(policy: Policy) -> None:
    codes = run_check(policy, "src/pkg/_foundation/api.py", "def build(): return 1\n")
    assert codes == []
