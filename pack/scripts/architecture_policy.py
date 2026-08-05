"""Load and validate the deterministic architecture policy (architecture.toml)."""

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import cast


@dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    root: Path
    source_root: Path
    package: str
    package_root: Path
    domain_root: Path
    max_module_lines: int
    max_test_module_lines: int
    max_function_lines: int
    max_class_lines: int
    forbidden_module_stems: frozenset[str]
    exception_marker: str
    immutable_module_stems: frozenset[str]
    forbidden_import_roots: frozenset[str]
    forbidden_call_suffixes: frozenset[str]


def mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a TOML table")
    return cast("dict[str, object]", value)


def string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def integer(value: object, name: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def string_set(value: object, name: str) -> frozenset[str]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be an array of strings")
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise TypeError(f"{name} must be an array of strings")
    return frozenset(cast("list[str]", items))


def load_policy(root: Path) -> Policy:
    raw = mapping(tomllib.loads((root / "architecture.toml").read_text()), "root")
    project = mapping(raw["project"], "project")
    limits = mapping(raw["limits"], "limits")
    conventions = mapping(raw["conventions"], "conventions")
    domain = mapping(raw["domain"], "domain")
    source_root = root / string(project["source_root"], "project.source_root")
    package = string(project["package"], "project.package")
    package_root = source_root / package
    domain_root = package_root / string(domain["package"], "domain.package")
    return Policy(
        root=root,
        source_root=source_root,
        package=package,
        package_root=package_root,
        domain_root=domain_root,
        max_module_lines=integer(limits["max_module_lines"], "limits.max_module_lines"),
        max_test_module_lines=integer(
            limits["max_test_module_lines"], "limits.max_test_module_lines"
        ),
        max_function_lines=integer(limits["max_function_lines"], "limits.max_function_lines"),
        max_class_lines=integer(limits["max_class_lines"], "limits.max_class_lines"),
        forbidden_module_stems=string_set(
            conventions["forbidden_module_stems"], "conventions.forbidden_module_stems"
        ),
        exception_marker=string(conventions["exception_marker"], "conventions.exception_marker"),
        immutable_module_stems=string_set(
            domain["immutable_module_stems"], "domain.immutable_module_stems"
        ),
        forbidden_import_roots=string_set(
            domain["forbidden_import_roots"], "domain.forbidden_import_roots"
        ),
        forbidden_call_suffixes=string_set(
            domain["forbidden_call_suffixes"], "domain.forbidden_call_suffixes"
        ),
    )
