"""Prove system and product capabilities execute one validator rule set."""

import ast
from collections.abc import Callable
import importlib.util
import inspect
from pathlib import Path
import re
import shutil
import sys
from types import ModuleType
from typing import cast

import pytest

from scripts import capability_validator
from scripts.capability_validator import (
    CAPABILITY_RULE_IDS,
    ValidationReport,
)

SYSTEM_ROOT = Path("repoctl/modules/repository_generation")
PRODUCT_ROOT = Path("src/product/modules/billing")
RULE_FUNCTIONS: tuple[tuple[str, str], ...] = (
    ("CAP001", "required_structure_violations"),
    ("CAP002", "layer_direction_violations"),
    ("CAP003", "public_surface_violations"),
)
BYPASS_TERMS = frozenset({"bypass", "disable", "exclude", "exempt", "skip"})
ASSIGNMENT_NAME = re.compile(r"(?m)^\s*([A-Za-z0-9_.-]+)\s*=")
TABLE_NAME = re.compile(r"(?m)^\s*\[+([A-Za-z0-9_.-]+)")
SYSTEM_SKIP_NEEDLE = """\
def layer_direction_violations(capability: Capability) -> tuple[Violation, ...]:
    violations: list[Violation] = []
"""
SYSTEM_SKIP_REPLACEMENT = (
    'SYSTEM_PREFIX = "repo" + "ctl."\n\n\n'
    "def layer_direction_violations(capability: Capability) -> tuple[Violation, ...]:\n"
    "    if capability.module.startswith(SYSTEM_PREFIX):\n"
    "        return ()\n"
    "    violations: list[Violation] = []\n"
)

type ValidateFunction = Callable[[Path, Path, str | None], ValidationReport]


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_policy(root: Path) -> None:
    _ = (root / "architecture.toml").write_text(
        """\
[ownership.roots]
FOUNDATION = ["architecture.toml", "repoctl"]
PRODUCT = ["src/product/modules"]
DERIVED = ["derived"]
DECLARATION = [".repo"]
""",
        encoding="utf-8",
    )


def _seed_product(root: Path) -> None:
    contents = {
        Path("api.py"): '"""Stable product capability surface."""\n',
        Path("domain/model.py"): '"""Product domain model."""\n',
        Path("application/use_case.py"): '"""Product use case."""\n',
        Path("adapters/inbound/cli.py"): '"""Product inbound adapter."""\n',
        Path("adapters/outbound/store.py"): '"""Product outbound adapter."""\n',
    }
    for relative, content in contents.items():
        target = root / PRODUCT_ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(content, encoding="utf-8")


def _validate(
    validator: ModuleType,
    repository: Path,
    root: Path,
    ownership: str,
) -> ValidationReport:
    validate = cast("ValidateFunction", validator.validate_capability)
    return validate(repository, root, ownership)


def _seed_rule_probes(repository: Path) -> None:
    for capability_root, dependency in (
        (
            SYSTEM_ROOT,
            "repoctl.modules.repository_generation.application",
        ),
        (
            PRODUCT_ROOT,
            "product.modules.billing.application",
        ),
    ):
        shutil.rmtree(repository / capability_root / "adapters/outbound")
        _ = (repository / capability_root / "domain/rule_probe.py").write_text(
            f"from {dependency} import rule_probe\n",
            encoding="utf-8",
        )

    consumers = {
        Path("tests/system_rule_probe.py"): (
            "from repoctl.modules.repository_generation.domain import intents\n"
        ),
        Path("tests/product_rule_probe.py"): ("from product.modules.billing.domain import model\n"),
    }
    for relative, content in consumers.items():
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(content, encoding="utf-8")


def build_reports(
    source_root: Path,
    tmp_path: Path,
    validator: ModuleType = capability_validator,
    *,
    probe_rules: bool = False,
) -> tuple[ValidationReport, ValidationReport]:
    repository = tmp_path / ("rule-probe-repository" if probe_rules else "repository")
    repository.mkdir()
    _write_policy(repository)
    _ = shutil.copytree(source_root / SYSTEM_ROOT, repository / SYSTEM_ROOT)
    _seed_product(repository)
    if probe_rules:
        _seed_rule_probes(repository)
    system = _validate(validator, repository, SYSTEM_ROOT, "FOUNDATION")
    product = _validate(validator, repository, PRODUCT_ROOT, "PRODUCT")
    return system, product


def observed_rule_ids(report: ValidationReport) -> frozenset[str]:
    return frozenset(item.code for item in report.violations)


def assert_identical_rule_sets(
    system: ValidationReport,
    product: ValidationReport,
) -> None:
    expected = frozenset(CAPABILITY_RULE_IDS)
    system_rules = observed_rule_ids(system)
    product_rules = observed_rule_ids(product)
    assert system_rules == product_rules == expected, (
        f"system observed rules {sorted(system_rules)} != product observed rules "
        f"{sorted(product_rules)} != expected {sorted(expected)}"
    )
    assert system.rule_ids == product.rule_ids == CAPABILITY_RULE_IDS


def load_system_rule_body_skip_mutant(tmp_path: Path) -> ModuleType:
    source_path = inspect.getsourcefile(capability_validator)
    assert source_path is not None
    source = Path(source_path).read_text(encoding="utf-8")
    assert source.count(SYSTEM_SKIP_NEEDLE) == 1
    target = tmp_path / "capability_validator_system_rule_body_skip_mutant.py"
    _ = target.write_text(
        source.replace(SYSTEM_SKIP_NEEDLE, SYSTEM_SKIP_REPLACEMENT),
        encoding="utf-8",
    )
    module_name = "_capability_validator_system_rule_body_skip_mutant"
    spec = importlib.util.spec_from_file_location(module_name, target)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[module_name]
    return module


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _branch_expressions(node: ast.AST) -> tuple[str, ...]:
    return tuple(
        ast.unparse(candidate.test).casefold()
        if isinstance(candidate, (ast.If, ast.IfExp))
        else ast.unparse(candidate.subject).casefold()
        for candidate in ast.walk(node)
        if isinstance(candidate, (ast.If, ast.IfExp, ast.Match))
    )


def _configuration_names(source_root: Path) -> frozenset[str]:
    architecture = source_root / "architecture.toml"
    if not architecture.is_file():
        architecture = source_root / "architecture.toml.jinja"
    text = architecture.read_text(encoding="utf-8")
    assignments = tuple(match.group(1) for match in ASSIGNMENT_NAME.finditer(text))
    tables = tuple(match.group(1) for match in TABLE_NAME.finditer(text))
    return frozenset(name.casefold() for name in (*assignments, *tables))


def assert_no_repoctl_rule_bypass(source_root: Path) -> None:
    source_path = inspect.getsourcefile(capability_validator)
    assert source_path is not None
    source = Path(source_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=source_path)
    validator = _function(tree, "validate_capability")
    direct_calls = {
        node.func.id
        for node in ast.walk(validator)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert direct_calls >= {function_name for _, function_name in RULE_FUNCTIONS}
    assert not _branch_expressions(validator)

    for _, name in RULE_FUNCTIONS:
        branches = _branch_expressions(_function(tree, name))
        assert all("ownership" not in expression for expression in branches)
        assert all("repoctl" not in expression for expression in branches)

    environment_access = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr.casefold() in {"environ", "getenv"}
    }
    assert environment_access == set()
    assert all(
        not ("repoctl" in name and any(term in name for term in BYPASS_TERMS))
        for name in _configuration_names(source_root)
    )


def test_system_and_product_execute_identical_rule_identifier_sets(
    tmp_path: Path,
) -> None:
    system, product = build_reports(repository_root(), tmp_path)

    assert system.capability.ownership == "FOUNDATION"
    assert product.capability.ownership == "PRODUCT"
    assert system.violations == ()
    assert product.violations == ()

    system_probe, product_probe = build_reports(
        repository_root(),
        tmp_path,
        probe_rules=True,
    )
    assert_identical_rule_sets(system_probe, product_probe)


def test_rule_set_equality_detects_a_system_only_skip(tmp_path: Path) -> None:
    mutant = load_system_rule_body_skip_mutant(tmp_path)
    system, product = build_reports(
        repository_root(),
        tmp_path,
        validator=mutant,
        probe_rules=True,
    )

    assert "CAP002" in system.rule_ids
    assert "CAP002" not in observed_rule_ids(system)
    with pytest.raises(AssertionError, match="system observed rules"):
        assert_identical_rule_sets(system, product)


def test_repository_has_no_repoctl_rule_bypass() -> None:
    assert_no_repoctl_rule_bypass(repository_root())
