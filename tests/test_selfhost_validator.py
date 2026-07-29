"""Run the generated capability-parity contract against its canonical template."""

import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "template/tests/repoctl/test_capability_contract.py"


def _load_contract() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_template_capability_contract",
        CONTRACT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACT = _load_contract()


def test_template_system_and_product_execute_identical_rules(
    tmp_path: Path,
) -> None:
    system, product = CONTRACT.build_reports(REPO_ROOT / "template", tmp_path)
    assert system.violations == ()
    assert product.violations == ()
    CONTRACT.assert_identical_rule_sets(system, product)


def test_template_contract_detects_a_system_only_rule_skip(
    tmp_path: Path,
) -> None:
    system, product = CONTRACT.build_reports(REPO_ROOT / "template", tmp_path)
    mutant = CONTRACT.replace(
        system,
        rule_ids=tuple(rule for rule in system.rule_ids if rule != "CAP002"),
    )

    try:
        CONTRACT.assert_identical_rule_sets(mutant, product)
    except AssertionError:
        pass
    else:
        raise AssertionError("The parity contract accepted a system-only rule skip.")


def test_template_has_no_repoctl_rule_bypass() -> None:
    CONTRACT.assert_no_repoctl_rule_bypass(REPO_ROOT / "template")
