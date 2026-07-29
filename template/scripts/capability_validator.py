#!/usr/bin/env python3
"""Validate one structural contract for system and product capabilities."""

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import sys
import tomllib
from typing import Literal, cast

from scripts.architecture_rules import Violation, is_under, violation
from scripts.ownership import OwnershipPathError, classify_path
from scripts.ownership_policy import OwnershipPolicyError, load_ownership_policy

type CapabilityOwnership = Literal["FOUNDATION", "PRODUCT"]
type CapabilityLayer = Literal["api", "domain", "application", "adapters", "bootstrap"]

CAPABILITY_RULE_IDS = ("CAP001", "CAP002", "CAP003")
REQUIRED_STRUCTURE = (
    (Path("api.py"), "file"),
    (Path("domain"), "directory"),
    (Path("application"), "directory"),
    (Path("adapters/inbound"), "directory"),
    (Path("adapters/outbound"), "directory"),
)
CAPABILITY_LAYERS: frozenset[CapabilityLayer] = frozenset(
    {"api", "domain", "application", "adapters", "bootstrap"}
)
DOMAIN_ALLOWED_IMPORT_ROOTS = sys.stdlib_module_names | frozenset(("icontract",))
ALLOWED_DEPENDENCIES: tuple[tuple[CapabilityLayer, frozenset[CapabilityLayer]], ...] = (
    ("api", CAPABILITY_LAYERS),
    ("domain", frozenset({"domain"})),
    ("application", frozenset({"domain", "application"})),
    ("adapters", frozenset({"domain", "application", "adapters"})),
    ("bootstrap", CAPABILITY_LAYERS),
)
REPOSITORY_PYTHON_ROOTS = ("repoctl", "src", "tests", "verification", "scripts")


class CapabilityConfigurationError(ValueError):
    """Raised when a capability root or ownership argument is inconsistent."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Capability:
    repository_root: Path
    root: Path
    module: str
    ownership: CapabilityOwnership


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationReport:
    capability: Capability
    rule_ids: tuple[str, ...]
    violations: tuple[Violation, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandArguments:
    repository_root: Path
    root: Path
    ownership: str | None


def _module_parts(path: Path, repository_root: Path) -> tuple[str, ...]:
    relative = path.relative_to(repository_root)
    parts = list(relative.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return tuple(parts)


def _capability_module(root: Path, repository_root: Path) -> str:
    relative = root.relative_to(repository_root)
    parts = relative.parts[1:] if relative.parts[0] == "src" else relative.parts
    return ".".join(parts)


def _import_base(
    node: ast.ImportFrom,
    source: Path,
    repository_root: Path,
) -> tuple[str, ...]:
    module = tuple(node.module.split(".")) if node.module else ()
    if node.level == 0:
        return module
    package = list(_module_parts(source, repository_root))
    if source.name != "__init__.py":
        package = package[:-1]
    parents = node.level - 1
    if parents > len(package):
        return ()
    return (*package[: len(package) - parents], *module)


def import_targets(
    node: ast.Import | ast.ImportFrom,
    source: Path,
    repository_root: Path,
) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    base = _import_base(node, source, repository_root)
    targets: list[str] = []
    for alias in node.names:
        parts = base if alias.name == "*" else (*base, *alias.name.split("."))
        if parts:
            targets.append(".".join(parts))
    return tuple(targets)


def _source_layer(path: Path, capability_root: Path) -> CapabilityLayer | None:
    relative = path.relative_to(capability_root)
    if relative == Path("api.py"):
        return "api"
    if relative == Path("bootstrap.py"):
        return "bootstrap"
    if relative.parts[0] in {"domain", "application", "adapters"}:
        return cast("CapabilityLayer", relative.parts[0])
    return None


def _target_layer(target: str, capability_module: str) -> CapabilityLayer | None:
    prefix = f"{capability_module}."
    if not target.startswith(prefix):
        return None
    layer = target.removeprefix(prefix).split(".", maxsplit=1)[0]
    if layer not in CAPABILITY_LAYERS:
        return None
    return layer


def _allowed_dependencies(layer: CapabilityLayer) -> frozenset[CapabilityLayer]:
    return next(allowed for candidate, allowed in ALLOWED_DEPENDENCIES if candidate == layer)


def _dependency_is_allowed(
    layer: CapabilityLayer,
    target: str,
    target_layer: CapabilityLayer | None,
) -> bool:
    if target_layer is not None:
        return target_layer in _allowed_dependencies(layer)
    if layer == "domain":
        return target.partition(".")[0] in DOMAIN_ALLOWED_IMPORT_ROOTS
    return True


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _repository_python_files(root: Path) -> tuple[Path, ...]:
    paths = set(root.glob("*.py"))
    for name in REPOSITORY_PYTHON_ROOTS:
        candidate = root / name
        if candidate.is_dir():
            paths.update(path for path in candidate.rglob("*.py") if path.is_file())
    return tuple(sorted(paths))


def required_structure_violations(capability: Capability) -> tuple[Violation, ...]:
    violations: list[Violation] = []
    for relative, kind in REQUIRED_STRUCTURE:
        path = capability.root / relative
        present = path.is_file() if kind == "file" else path.is_dir()
        if not present:
            violations.append(
                Violation(
                    path=path,
                    line=1,
                    code="CAP001",
                    message=f"Capability requires {relative.as_posix()} ({kind}).",
                )
            )
    return tuple(violations)


def layer_direction_violations(capability: Capability) -> tuple[Violation, ...]:
    violations: list[Violation] = []
    for path in _python_files(capability.root):
        layer = _source_layer(path, capability.root)
        if layer is None:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            violations.append(
                Violation(
                    path=path,
                    line=error.lineno or 1,
                    code="CAP002",
                    message=f"Cannot inspect capability dependencies: {error.msg}",
                )
            )
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in import_targets(node, path, capability.repository_root):
                target_layer = _target_layer(target, capability.module)
                if not _dependency_is_allowed(layer, target, target_layer):
                    dependency = target_layer or target.partition(".")[0]
                    violations.append(
                        violation(
                            path,
                            node,
                            "CAP002",
                            f"{layer} must not depend on {dependency}: {target}",
                        )
                    )
    return tuple(violations)


def _uses_public_surface(target: str, capability_module: str) -> bool:
    api = f"{capability_module}.api"
    return target == api or target.startswith(f"{api}.")


def public_surface_violations(capability: Capability) -> tuple[Violation, ...]:
    violations: list[Violation] = []
    module_prefix = f"{capability.module}."
    for path in _repository_python_files(capability.repository_root):
        if is_under(path, capability.root):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in import_targets(node, path, capability.repository_root):
                imports_capability = target == capability.module or target.startswith(module_prefix)
                if imports_capability and not _uses_public_surface(target, capability.module):
                    violations.append(
                        violation(
                            path,
                            node,
                            "CAP003",
                            f"Import capability through {capability.module}.api, not {target}.",
                        )
                    )
    return tuple(violations)


def _capability(
    repository_root: Path,
    root: Path,
    requested_ownership: str | None,
) -> Capability:
    resolved_repository = repository_root.resolve()
    resolved_root = root.resolve() if root.is_absolute() else (resolved_repository / root).resolve()
    try:
        relative = resolved_root.relative_to(resolved_repository)
    except ValueError as error:
        raise CapabilityConfigurationError(
            "Capability root must be inside the repository."
        ) from error
    policy = load_ownership_policy(resolved_repository)
    actual_ownership = str(classify_path(relative, policy))
    if actual_ownership not in {"FOUNDATION", "PRODUCT"}:
        raise CapabilityConfigurationError(
            f"Capability root belongs to {actual_ownership}, expected FOUNDATION or PRODUCT."
        )
    if requested_ownership is not None and requested_ownership != actual_ownership:
        raise CapabilityConfigurationError(
            f"Requested {requested_ownership} ownership but {relative} is {actual_ownership}."
        )
    return Capability(
        repository_root=resolved_repository,
        root=resolved_root,
        module=_capability_module(resolved_root, resolved_repository),
        ownership=cast("CapabilityOwnership", actual_ownership),
    )


def validate_capability(
    repository_root: Path,
    root: Path,
    ownership: str | None = None,
) -> ValidationReport:
    capability = _capability(repository_root, root, ownership)
    violations = (
        *required_structure_violations(capability),
        *layer_direction_violations(capability),
        *public_surface_violations(capability),
    )
    return ValidationReport(
        capability=capability,
        rule_ids=CAPABILITY_RULE_IDS,
        violations=tuple(
            sorted(violations, key=lambda item: (str(item.path), item.line, item.code))
        ),
    )


def discovered_capabilities(
    repository_root: Path,
    package_root: Path,
) -> tuple[tuple[Path, CapabilityOwnership], ...]:
    parents: tuple[tuple[Path, CapabilityOwnership], ...] = (
        (repository_root / "repoctl/modules", "FOUNDATION"),
        (package_root / "modules", "PRODUCT"),
    )
    return tuple(
        (path, ownership)
        for parent, ownership in parents
        if parent.is_dir()
        for path in sorted(parent.iterdir())
        if path.is_dir()
    )


def validate_repository_capabilities(
    repository_root: Path,
    package_root: Path,
) -> tuple[Violation, ...]:
    return tuple(
        violation
        for root, ownership in discovered_capabilities(repository_root, package_root)
        for violation in validate_capability(repository_root, root, ownership).violations
    )


def _arguments(argv: list[str]) -> CommandArguments:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    _ = parser.add_argument("--root", type=Path, required=True)
    _ = parser.add_argument("--ownership", choices=("FOUNDATION", "PRODUCT"))
    values = cast("dict[str, object]", vars(parser.parse_args(argv)))
    repository_root = values["repository_root"]
    root = values["root"]
    ownership = values["ownership"]
    if not isinstance(repository_root, Path) or not isinstance(root, Path):
        raise CapabilityConfigurationError("Repository and capability roots must be paths.")
    if ownership is not None and not isinstance(ownership, str):
        raise CapabilityConfigurationError("Capability ownership must be a string.")
    return CommandArguments(
        repository_root=repository_root,
        root=root,
        ownership=ownership,
    )


def main(argv: list[str]) -> int:
    arguments = _arguments(argv)
    try:
        report = validate_capability(
            arguments.repository_root,
            arguments.root,
            arguments.ownership,
        )
    except (
        OSError,
        tomllib.TOMLDecodeError,
        CapabilityConfigurationError,
        OwnershipPathError,
        OwnershipPolicyError,
    ) as error:
        print(f"Capability validation could not run: {error}", file=sys.stderr)
        return 2
    relative = report.capability.root.relative_to(report.capability.repository_root)
    identity = f"root={relative} ownership={report.capability.ownership}"
    rules = ",".join(report.rule_ids)
    print(f"Capability validation: {identity} rules={rules}")
    if report.violations:
        for item in report.violations:
            print(item.render(report.capability.repository_root), file=sys.stderr)
        return 1
    print("Capability structure passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
