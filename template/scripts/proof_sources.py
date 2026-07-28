"""Discover public core behaviors, contracts, and executable oracles."""

import ast
from collections.abc import Iterable
from pathlib import Path
import re

from scripts.proof_ast import direct_invoked_targets, dotted_name, import_bindings
from scripts.proof_catalog import ProofPolicy
from scripts.proof_model import (
    ContractLink,
    Definition,
    DiscoveryError,
    ImportBindings,
    OracleShape,
    SourceTarget,
)

PROPERTY_DESCRIPTION = re.compile(r"^PROPERTY\[([A-Z][A-Z0-9-]+)\](?:: .+)?$")
CONTRACT_DECORATORS = frozenset({"require", "ensure", "invariant"})
ORACLE_FORBIDDEN_NODES = (
    ast.AsyncWith,
    ast.Await,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.TryStar,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join(parts)


def _module_path(module: str, source_root: Path) -> Path:
    relative = Path().joinpath(*module.split("."))
    file_path = source_root / relative.with_suffix(".py")
    if file_path.is_file():
        return file_path
    package_path = source_root / relative
    if package_path.is_dir():
        return package_path
    raise DiscoveryError(f"Module '{module}' does not exist under {source_root}")


def _module_file(module: str, source_root: Path) -> Path | None:
    path = _module_path(module, source_root)
    candidate = path / "__init__.py" if path.is_dir() else path
    return candidate if candidate.is_file() else None


def behavior_files(policy: ProofPolicy) -> tuple[Path, ...]:
    files: set[Path] = set()
    for module in policy.behavior_roots:
        path = _module_path(module, policy.source_root)
        if path.is_file():
            files.add(path)
        else:
            files.update(path.rglob("*.py"))
    return tuple(
        sorted(
            path
            for path in files
            if path.is_file()
            and path.stem not in policy.excluded_module_stems
            and not any(part.startswith(".") for part in path.parts)
        )
    )


def _literal_description(call: ast.Call) -> str | None:
    descriptions = [keyword.value for keyword in call.keywords if keyword.arg == "description"]
    if len(descriptions) != 1:
        return None
    value = descriptions[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return None
    return value.value


def _contract_link(
    decorator: ast.expr,
    path: Path,
    imports: ImportBindings,
) -> ContractLink | None:
    if not isinstance(decorator, ast.Call):
        return None
    name = dotted_name(decorator.func).split(".")[-1]
    if name not in CONTRACT_DECORATORS:
        return None
    description = _literal_description(decorator)
    match = PROPERTY_DESCRIPTION.fullmatch(description) if description is not None else None
    return ContractLink(
        path=path,
        line=decorator.lineno,
        decorator=name,
        property_id=match.group(1) if match is not None else None,
        description=description,
        invoked_targets=direct_invoked_targets(decorator, imports),
    )


def _contract_links(
    decorators: Iterable[ast.expr],
    path: Path,
    imports: ImportBindings,
) -> tuple[ContractLink, ...]:
    return tuple(
        link
        for decorator in decorators
        if (link := _contract_link(decorator, path, imports)) is not None
    )


def _public_name(name: str) -> bool:
    return not name.startswith("_")


def _target(module: str, qualname: str) -> str:
    return f"{module}:{qualname}"


def _source_target(
    path: Path,
    module: str,
    qualname: str,
    node: Definition,
    kind: str,
    imports: ImportBindings,
) -> SourceTarget:
    return SourceTarget(
        path=path,
        line=node.lineno,
        target=_target(module, qualname),
        kind=kind,
        contracts=_contract_links(node.decorator_list, path, imports),
    )


def _class_targets(
    path: Path,
    module: str,
    node: ast.ClassDef,
    imports: ImportBindings,
) -> tuple[SourceTarget, ...]:
    targets = [_source_target(path, module, node.name, node, "class", imports)]
    targets.extend(
        _source_target(
            path,
            module,
            f"{node.name}.{member.name}",
            member,
            "method",
            imports,
        )
        for member in node.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _public_name(member.name)
    )
    return tuple(targets)


def _targets_in_file(path: Path, source_root: Path) -> tuple[SourceTarget, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = _module_name(path, source_root)
    imports = import_bindings(tree)
    targets: list[SourceTarget] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _public_name(node.name):
            targets.append(
                _source_target(path, module, node.name, node, "function", imports)
            )
        elif isinstance(node, ast.ClassDef) and _public_name(node.name):
            targets.extend(_class_targets(path, module, node, imports))
    return tuple(targets)


def discover_behavior_targets(policy: ProofPolicy) -> tuple[SourceTarget, ...]:
    return tuple(
        target
        for path in behavior_files(policy)
        for target in _targets_in_file(path, policy.source_root)
    )


def _named_definition(nodes: Iterable[ast.stmt], name: str) -> Definition | None:
    for node in nodes:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    return None


def _find_qualified_node(tree: ast.Module, qualname: str) -> Definition | None:
    nodes: list[ast.stmt] = list(tree.body)
    current: Definition | None = None
    parts = qualname.split(".")
    for index, part in enumerate(parts):
        current = _named_definition(nodes, part)
        if current is None:
            return None
        if index < len(parts) - 1:
            if not isinstance(current, ast.ClassDef):
                return None
            nodes = list(current.body)
    return current


def _resolved_definition(
    source_root: Path,
    target: str,
    *,
    label: str,
) -> tuple[Path, str, str, Definition] | None:
    module, separator, qualname = target.partition(":")
    if not separator:
        raise DiscoveryError(f"Invalid {label} '{target}'")
    path = _module_file(module, source_root)
    if path is None:
        return None
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = _find_qualified_node(tree, qualname)
    if node is None:
        return None
    return path, module, qualname, node


def discover_target(source_root: Path, target: str) -> SourceTarget | None:
    resolved = _resolved_definition(source_root, target, label="target")
    if resolved is None:
        return None
    path, module, qualname, node = resolved
    kind = "class" if isinstance(node, ast.ClassDef) else "function"
    if "." in qualname:
        kind = "method"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return _source_target(path, module, qualname, node, kind, import_bindings(tree))


def _imported_modules(tree: ast.Module) -> frozenset[str]:
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return frozenset(imported)


def _called_names(node: ast.AST) -> frozenset[str]:
    return frozenset(
        dotted_name(candidate.func)
        for candidate in ast.walk(node)
        if isinstance(candidate, ast.Call)
    )


def _forbidden_node_names(node: ast.AST) -> frozenset[str]:
    return frozenset(
        type(candidate).__name__
        for candidate in ast.walk(node)
        if isinstance(candidate, ORACLE_FORBIDDEN_NODES)
    )


def discover_oracle(source_root: Path, target: str) -> OracleShape | None:
    resolved = _resolved_definition(source_root, target, label="oracle target")
    if resolved is None:
        return None
    path, module, _, node = resolved
    if isinstance(node, ast.ClassDef):
        return None
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return OracleShape(
        path=path,
        line=node.lineno,
        target=target,
        module_stem=module.rpartition(".")[2],
        is_async=isinstance(node, ast.AsyncFunctionDef),
        return_annotation=dotted_name(node.returns) if node.returns is not None else "",
        has_variadic_parameters=node.args.vararg is not None or node.args.kwarg is not None,
        called_names=_called_names(node),
        imported_modules=_imported_modules(tree),
        forbidden_nodes=_forbidden_node_names(node),
    )
