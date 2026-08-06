"""AST name binding and direct-call resolution for proof discovery.

This is machinery for `proof_sources.py` and `proof_invocations.py`. It
emits no PROOF code.
"""

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scripts.proof_model import (
    FunctionDefinition,
    ImportBindings,
    ModuleImport,
    Scope,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

_SCOPE_BARRIERS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _expression_parts(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        prefix = _expression_parts(node.value)
        return (*prefix, node.attr) if prefix else ()
    return ()


def _add_unique_binding[BindingKey](
    bindings: dict[BindingKey, str],
    ambiguous: set[BindingKey],
    key: BindingKey,
    value: str,
) -> None:
    existing = bindings.get(key)
    if key in ambiguous:
        return
    if existing is None or existing == value:
        bindings[key] = value
        return
    _ = bindings.pop(key, None)
    ambiguous.add(key)


def walk_scope(node: ast.Module | FunctionDefinition) -> Iterable[ast.AST]:
    stack: list[ast.AST] = list(reversed(node.body))
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, _SCOPE_BARRIERS):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(current))))


def function_receiver(node: FunctionDefinition) -> str | None:
    positional = (*node.args.posonlyargs, *node.args.args)
    return positional[0].arg if positional else None


def _class_scopes(node: ast.ClassDef, prefix: str) -> tuple[Scope, ...]:
    class_key = f"{prefix}.{node.name}" if prefix else node.name
    scopes: list[Scope] = []
    for member in node.body:
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append(
                Scope(
                    key=f"{class_key}.{member.name}",
                    node=member,
                    class_key=class_key,
                    receiver_name=function_receiver(member),
                )
            )
        elif isinstance(member, ast.ClassDef):
            scopes.extend(_class_scopes(member, class_key))
    return tuple(scopes)


def module_scopes(tree: ast.Module) -> tuple[Scope, ...]:
    scopes = [Scope(key="<module>", node=tree, class_key=None, receiver_name=None)]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append(
                Scope(
                    key=node.name,
                    node=node,
                    class_key=None,
                    receiver_name=function_receiver(node),
                )
            )
        elif isinstance(node, ast.ClassDef):
            scopes.extend(_class_scopes(node, ""))
    return tuple(scopes)


def _assignment_names(node: ast.Module | FunctionDefinition) -> frozenset[str]:
    names: set[str] = set()
    for candidate in walk_scope(node):
        if isinstance(candidate, ast.Name) and isinstance(candidate.ctx, ast.Store):
            names.add(candidate.id)
        elif isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(candidate.name)
    return frozenset(names)


@dataclass(slots=True)
class _ImportAccumulator:
    symbols: dict[str, str]
    modules: dict[tuple[str, ...], str]
    ambiguous_symbols: set[str]
    ambiguous_modules: set[tuple[str, ...]]

    def add_from(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            _add_unique_binding(
                self.symbols,
                self.ambiguous_symbols,
                alias.asname or alias.name,
                f"{node.module}:{alias.name}",
            )

    def add_import(self, node: ast.Import) -> None:
        for alias in node.names:
            prefix = (alias.asname,) if alias.asname else tuple(alias.name.split("."))
            _add_unique_binding(
                self.modules,
                self.ambiguous_modules,
                prefix,
                alias.name,
            )


def _import_accumulator(tree: ast.Module) -> _ImportAccumulator:
    accumulator = _ImportAccumulator(
        symbols={},
        modules={},
        ambiguous_symbols=set(),
        ambiguous_modules=set(),
    )
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            accumulator.add_from(node)
        elif isinstance(node, ast.Import):
            accumulator.add_import(node)
    return accumulator


def _resolved_import_symbols(
    accumulator: _ImportAccumulator,
    shadowed: frozenset[str],
) -> dict[str, str]:
    return {
        name: target
        for name, target in accumulator.symbols.items()
        if name not in shadowed and name not in accumulator.ambiguous_symbols
    }


def _resolved_module_imports(
    accumulator: _ImportAccumulator,
    shadowed: frozenset[str],
) -> tuple[ModuleImport, ...]:
    imports = (
        ModuleImport(module=module, prefix=prefix)
        for prefix, module in accumulator.modules.items()
        if prefix not in accumulator.ambiguous_modules and (not prefix or prefix[0] not in shadowed)
    )
    return tuple(
        sorted(
            imports,
            key=lambda item: (-len(item.prefix), item.prefix, item.module),
        )
    )


def import_bindings(tree: ast.Module) -> ImportBindings:
    accumulator = _import_accumulator(tree)
    shadowed = _assignment_names(tree)
    return ImportBindings(
        symbols=_resolved_import_symbols(accumulator, shadowed),
        modules=_resolved_module_imports(accumulator, shadowed),
    )


def scope_shadowed_names(scope: Scope, imports: ImportBindings) -> frozenset[str]:
    imported_names = set(imports.symbols)
    imported_names.update(item.prefix[0] for item in imports.modules if item.prefix)
    shadowed = _argument_names(scope.node)
    shadowed.update(_assignment_names(scope.node))
    return frozenset(shadowed & imported_names)


def _argument_names(node: ast.Module | FunctionDefinition) -> set[str]:
    if isinstance(node, ast.Module):
        return set()
    arguments = node.args
    names = {
        argument.arg
        for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


def _module_import_match(
    parts: tuple[str, ...],
    imports: tuple[ModuleImport, ...],
) -> ModuleImport | None:
    matches = tuple(
        item
        for item in imports
        if len(parts) > len(item.prefix) and parts[: len(item.prefix)] == item.prefix
    )
    if not matches:
        return None
    longest = len(matches[0].prefix)
    best = tuple(item for item in matches if len(item.prefix) == longest)
    return best[0] if len({item.module for item in best}) == 1 else None


def _resolve_module_symbol(
    parts: tuple[str, ...],
    imports: tuple[ModuleImport, ...],
) -> str | None:
    match = _module_import_match(parts, imports)
    if match is None:
        return None
    suffix = ".".join(parts[len(match.prefix) :])
    return f"{match.module}:{suffix}" if suffix else None


def resolve_imported_symbol(
    node: ast.AST,
    imports: ImportBindings,
    shadowed: frozenset[str],
) -> str | None:
    parts = _expression_parts(node)
    if not parts or parts[0] in shadowed:
        return None
    imported_symbol = imports.symbols.get(parts[0])
    if imported_symbol is None:
        return _resolve_module_symbol(parts, imports.modules)
    suffix = ".".join(parts[1:])
    return f"{imported_symbol}.{suffix}" if suffix else imported_symbol


def _node_binding_names(node: ast.AST) -> frozenset[str]:
    names = {
        candidate.id
        for candidate in ast.walk(node)
        if isinstance(candidate, ast.Name) and isinstance(candidate.ctx, ast.Store)
    }
    for candidate in ast.walk(node):
        if not isinstance(candidate, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = candidate.args
        names.update(
            argument.arg
            for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
        )
        if arguments.vararg is not None:
            names.add(arguments.vararg.arg)
        if arguments.kwarg is not None:
            names.add(arguments.kwarg.arg)
    return frozenset(names)


def direct_invoked_targets(
    node: ast.AST,
    imports: ImportBindings,
) -> frozenset[str]:
    shadowed = _node_binding_names(node)
    return frozenset(
        target
        for candidate in ast.walk(node)
        if isinstance(candidate, ast.Call)
        if (target := resolve_imported_symbol(candidate.func, imports, shadowed)) is not None
    )
