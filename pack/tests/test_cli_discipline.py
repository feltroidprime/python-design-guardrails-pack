"""Tests for agent-native CLI architecture rules (ARCH021-ARCH025)."""

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


def test_arch024_rejects_literal_command_registration(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def build(commands: object) -> None:\n    commands.add_parser('hidden')\n",
    )
    assert codes == ["ARCH024"]


def test_arch024_rejects_dynamic_command_registration(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def build(commands: object, name: str) -> None:\n    commands.add_parser(name)\n",
    )
    assert codes == ["ARCH024"]


def test_arch024_rejects_uncataloged_parser_aliases(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def build(commands: object, spec: object) -> None:\n"
        "    commands.add_parser(spec.name.value, aliases=['hidden'])\n",
    )
    assert codes == ["ARCH024"]


def test_arch024_rejects_indirect_parser_registration(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def build(commands: object) -> None:\n"
        "    register = commands.add_parser\n"
        "    register('hidden')\n",
    )
    assert codes == ["ARCH024"]


def test_arch024_rejects_dynamic_registration_outside_the_cli(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/extra.py",
        "def build(commands: object) -> None:\n"
        "    register = getattr(commands, 'add_parser')\n"
        "    register('hidden')\n",
    )
    assert codes == ["ARCH024"]


def test_arch024_allows_unrelated_dynamic_lookup_in_the_cli(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def value(request: object) -> object:\n    return getattr(request, 'value')\n",
    )
    assert codes == []


def test_arch024_rejects_unpacking_registration_keywords(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def build(commands: object) -> None:\n"
        "    for spec in COMMAND_CATALOG:\n"
        "        commands.add_parser(spec.name.value, **{'aliases': ['hidden']})\n",
    )
    assert codes == ["ARCH024"]


def test_arch024_rejects_command_specs_outside_the_catalog(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/extra.py",
        "def register() -> object:\n    return CommandSpec(name='hidden')\n",
    )
    assert codes == ["ARCH024"]


@pytest.mark.parametrize(
    "input_policy",
    [
        "",
        ", input_policy=InputPolicy(primary=InputMode.INLINE_JSON, stdin=StdinMode.FORBIDDEN)",
    ],
)
def test_arch025_rejects_catalog_entries_without_argument_primary_input(
    policy: Policy, input_policy: str
) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli_catalog.py",
        f"COMMAND_CATALOG = (CommandSpec(name='hidden'{input_policy}),)\n",
    )
    assert codes == ["ARCH025"]


def test_arch025_accepts_explicit_argument_primary_input(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli_catalog.py",
        "COMMAND_CATALOG = (CommandSpec(\n"
        "    name='visible',\n"
        "    input_policy=InputPolicy(\n"
        "        primary=InputMode.ARGUMENTS, stdin=StdinMode.FORBIDDEN\n"
        "    ),\n"
        "),)\n",
    )
    assert codes == []


def test_arch025_cannot_be_bypassed_by_aliasing_command_spec(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli_catalog.py",
        "from pkg.adapters.inbound.cli_contract import CommandSpec as Spec\n"
        "COMMAND_CATALOG = (Spec(name='hidden'),)\n",
    )
    assert codes == ["ARCH025"]


def test_arch025_cannot_be_bypassed_by_rebinding_command_spec(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli_catalog.py",
        "Spec = CommandSpec\nCOMMAND_CATALOG = (Spec(name='hidden'),)\n",
    )
    assert codes == ["ARCH025"]


@pytest.mark.parametrize(
    "binding",
    [
        "Spec = cli_contract.CommandSpec",
        "Spec: type[CommandSpec] = CommandSpec",
    ],
)
def test_arch025_cannot_be_bypassed_by_qualified_or_annotated_rebinding(
    policy: Policy, binding: str
) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli_catalog.py",
        f"{binding}\nCOMMAND_CATALOG = (Spec(name='hidden'),)\n",
    )
    assert codes == ["ARCH025"]


def test_catalog_driven_parser_construction_stays_silent(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "import argparse\n"
        "def build(parser: argparse.ArgumentParser) -> None:\n"
        "    commands = parser.add_subparsers()\n"
        "    for spec in COMMAND_CATALOG:\n"
        "        commands.add_parser(spec.name.value)\n",
    )
    assert codes == []


def test_catalog_loop_variable_name_is_not_an_architecture_contract(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/cli.py",
        "def build(parser: object) -> None:\n"
        "    commands = parser.add_subparsers()\n"
        "    for command_spec in COMMAND_CATALOG:\n"
        "        commands.add_parser(command_spec.name.value)\n",
    )
    assert codes == []


def test_controlled_module_entrypoint_stays_silent(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/__main__.py",
        "def main() -> int:\n    return 0\nraise SystemExit(main())\n",
    )
    assert codes == []
