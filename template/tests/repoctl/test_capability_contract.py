"""Prove system and product capabilities execute one validator rule set."""

import ast
from dataclasses import replace
import inspect
from pathlib import Path
import re
import shutil

import pytest

from scripts import capability_validator
from scripts.capability_validator import (
    CAPABILITY_RULE_IDS,
    ValidationReport,
    validate_capability,
)

SYSTEM_ROOT = Path("repoctl/modules/repository_generation")
PRODUCT_ROOT = Path("src/product/modules/billing")
RULE_FUNCTIONS = frozenset(
    {
        "required_structure_violations",
        "layer_direction_violations",
        "public_surface_violations",
    }
)
BYPASS_TERMS = frozenset({"bypass", "disable", "exclude", "exempt", "skip"})
ASSIGNMENT_NAME = re.compile(r"(?m)^\s*([A-Za-z0-9_.-]+)\s*=")
TABLE_NAME = re.compile(r"(?m)^\s*\[+([A-Za-z0-9_.-]+)")


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


def build_reports(
    source_root: Path,
    tmp_path: Path,
) -> tuple[ValidationReport, ValidationReport]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _write_policy(repository)
    _ = shutil.copytree(source_root / SYSTEM_ROOT, repository / SYSTEM_ROOT)
    _seed_product(repository)
    system = validate_capability(repository, SYSTEM_ROOT, "FOUNDATION")
    product = validate_capability(repository, PRODUCT_ROOT, "PRODUCT")
    return system, product


def assert_identical_rule_sets(
    system: ValidationReport,
    product: ValidationReport,
) -> None:
    expected = frozenset(CAPABILITY_RULE_IDS)
    system_rules = frozenset(system.rule_ids)
    product_rules = frozenset(product.rule_ids)
    assert len(system.rule_ids) == len(system_rules)
    assert len(product.rule_ids) == len(product_rules)
    assert system_rules == product_rules == expected, (
        f"system rules {sorted(system_rules)} != product rules "
        f"{sorted(product_rules)} != expected {sorted(expected)}"
    )


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
    assert direct_calls >= RULE_FUNCTIONS
    assert not _branch_expressions(validator)

    for name in RULE_FUNCTIONS:
        branches = _branch_expressions(_function(tree, name))
        assert all("ownership" not in expression for expression in branches)
        assert all(
            not ("repoctl" in expression and any(term in expression for term in BYPASS_TERMS))
            for expression in branches
        )

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
    assert_identical_rule_sets(system, product)


def test_rule_set_equality_detects_a_system_only_skip(tmp_path: Path) -> None:
    system, product = build_reports(repository_root(), tmp_path)
    mutant = replace(
        system,
        rule_ids=tuple(rule for rule in system.rule_ids if rule != "CAP002"),
    )

    with pytest.raises(AssertionError, match="system rules"):
        assert_identical_rule_sets(mutant, product)


def test_repository_has_no_repoctl_rule_bypass() -> None:
    assert_no_repoctl_rule_bypass(repository_root())
