"""Tests for agent-native CLI architecture rules (ARCH021-ARCH023)."""

from pathlib import Path

import pytest

from scripts.architecture_guard import check_files
from scripts.architecture_policy import Policy, load_policy
from tests.policy_tree import write_policy_tree

PACK = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy(tmp_path: Path) -> Policy:
    return load_policy(write_policy_tree(tmp_path))


def run_check(policy: Policy, relative: str, source: str) -> list[str]:
    path = policy.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return [item.code for item in check_files((path,), policy)]


def test_arch021_rejects_prompt_calls_in_production_paths(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def run() -> str:\n    return input('name: ')\n",
    )
    assert codes == ["ARCH021"]


def test_arch021_ignores_prompt_named_calls_outside_inbound_automation(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        "def confirm(client: object) -> None:\n    client.confirm()\n",
    )
    assert codes == []


def test_arch022_rejects_uncontrolled_process_exit(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "import sys\ndef run() -> None:\n    sys.exit(2)\n",
    )
    assert codes == ["ARCH022"]


def test_arch022_rejects_system_exit_outside_the_module_entrypoint(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def run() -> None:\n    raise SystemExit(2)\n",
    )
    assert codes == ["ARCH022"]


@pytest.mark.parametrize("framework", ["argparse", "click", "typer"])
def test_arch023_rejects_cli_framework_leakage(policy: Policy, framework: str) -> None:
    codes = run_check(
        policy,
        "src/pkg/application/use_cases.py",
        f"import {framework}\n",
    )
    assert codes == ["ARCH023"]


def test_arch023_allows_argparse_only_in_the_inbound_cli(policy: Policy) -> None:
    codes = run_check(policy, "src/pkg/adapters/inbound/cli.py", "import argparse\n")
    assert codes == []


def test_controlled_module_entrypoint_stays_silent(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/__main__.py",
        "def main() -> int:\n    return 0\nraise SystemExit(main())\n",
    )
    assert codes == []
