"""Conservative invocation analysis for exact proof target matching."""

import ast
from dataclasses import dataclass

from scripts.proof_ast import (
    import_bindings,
    module_scopes,
    resolve_imported_symbol,
    scope_shadowed_names,
    walk_scope,
)
from scripts.proof_model import (
    AssignmentRecord,
    BindingKey,
    ImportBindings,
    InvocationIndex,
    OriginExpression,
    Scope,
)


def _binding_key(node: ast.AST, scope: Scope) -> BindingKey | None:
    if isinstance(node, ast.Name):
        return ("local", scope.key, node.id)
    if _is_receiver_attribute(node, scope):
        return ("attribute", scope.class_key or "", node.attr)
    return None


def _is_receiver_attribute(node: ast.AST, scope: Scope) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and scope.class_key is not None
        and scope.receiver_name is not None
        and node.value.id == scope.receiver_name
    )


def _target_binding_keys(node: ast.AST, scope: Scope) -> tuple[BindingKey, ...]:
    direct = _binding_key(node, scope)
    if direct is not None:
        return (direct,)
    if not isinstance(node, (ast.Tuple, ast.List)):
        return ()
    return tuple(
        key
        for element in node.elts
        for key in _target_binding_keys(element, scope)
    )


def _origin_expression(
    value: ast.AST,
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
) -> OriginExpression:
    if isinstance(value, ast.Call):
        target = resolve_imported_symbol(value.func, imports, shadowed)
        return (
            OriginExpression(direct_target=target)
            if target is not None
            else OriginExpression(unknown=True)
        )
    reference = _binding_key(value, scope)
    return (
        OriginExpression(reference=reference)
        if reference is not None
        else OriginExpression(unknown=True)
    )


def _record_assignment(
    assignments: dict[BindingKey, list[OriginExpression]],
    keys: tuple[BindingKey, ...],
    expression: OriginExpression,
) -> None:
    for key in keys:
        assignments.setdefault(key, []).append(expression)


def _record_for_value(
    target: ast.AST,
    value: ast.AST | None,
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
) -> AssignmentRecord:
    expression = (
        _origin_expression(value, scope, imports, shadowed)
        if value is not None
        else OriginExpression(unknown=True)
    )
    return AssignmentRecord(
        keys=_target_binding_keys(target, scope),
        expression=expression,
    )


def _value_assignment_records(
    node: ast.AST,
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
) -> tuple[AssignmentRecord, ...]:
    if isinstance(node, ast.Assign):
        expression = _origin_expression(node.value, scope, imports, shadowed)
        return tuple(
            AssignmentRecord(keys=_target_binding_keys(target, scope), expression=expression)
            for target in node.targets
        )
    if isinstance(node, ast.AnnAssign):
        return (_record_for_value(node.target, node.value, scope, imports, shadowed),)
    if isinstance(node, ast.NamedExpr):
        return (_record_for_value(node.target, node.value, scope, imports, shadowed),)
    return ()


def _unknown_assignment_targets(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, (ast.AugAssign, ast.For, ast.AsyncFor, ast.comprehension)):
        return (node.target,)
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return tuple(item.optional_vars for item in node.items if item.optional_vars is not None)
    if isinstance(node, ast.Delete):
        return tuple(node.targets)
    return ()


def _assignment_records(
    node: ast.AST,
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
) -> tuple[AssignmentRecord, ...]:
    records = _value_assignment_records(node, scope, imports, shadowed)
    if records:
        return records
    unknown = OriginExpression(unknown=True)
    return tuple(
        AssignmentRecord(keys=_target_binding_keys(target, scope), expression=unknown)
        for target in _unknown_assignment_targets(node)
    )


def _collect_assignments(
    scopes: tuple[Scope, ...],
    imports: ImportBindings,
    shadows: dict[str, frozenset[str]],
) -> dict[BindingKey, list[OriginExpression]]:
    assignments: dict[BindingKey, list[OriginExpression]] = {}
    for scope in scopes:
        for node in walk_scope(scope.node):
            records = _assignment_records(node, scope, imports, shadows[scope.key])
            for record in records:
                _record_assignment(assignments, record.keys, record.expression)
    return assignments


@dataclass(slots=True)
class _OriginResolver:
    assignments: dict[BindingKey, list[OriginExpression]]
    cache: dict[BindingKey, str | None]

    def resolve(self, key: BindingKey, stack: frozenset[BindingKey]) -> str | None:
        if key in self.cache:
            return self.cache[key]
        result = self._resolve_uncached(key, stack)
        self.cache[key] = result
        return result

    def _resolve_uncached(
        self,
        key: BindingKey,
        stack: frozenset[BindingKey],
    ) -> str | None:
        if key in stack:
            return None
        expressions = tuple(self.assignments.get(key, []))
        if _ambiguous_origin_expressions(expressions):
            return None
        targets = self._resolve_expressions(expressions, stack | {key})
        return _unique_resolved_target(targets)

    def _resolve_expressions(
        self,
        expressions: tuple[OriginExpression, ...],
        stack: frozenset[BindingKey],
    ) -> tuple[str | None, ...]:
        return tuple(self._resolve_expression(expression, stack) for expression in expressions)

    def _resolve_expression(
        self,
        expression: OriginExpression,
        stack: frozenset[BindingKey],
    ) -> str | None:
        if expression.direct_target is not None:
            return expression.direct_target
        if not expression.reference[0]:
            return None
        return self.resolve(expression.reference, stack)


def _ambiguous_origin_expressions(
    expressions: tuple[OriginExpression, ...],
) -> bool:
    return not expressions or any(expression.unknown for expression in expressions)


def _unique_resolved_target(targets: tuple[str | None, ...]) -> str | None:
    if any(target is None for target in targets):
        return None
    unique = {target for target in targets if target is not None}
    return next(iter(unique)) if len(unique) == 1 else None


def _resolved_origins(
    assignments: dict[BindingKey, list[OriginExpression]],
) -> dict[BindingKey, str]:
    resolver = _OriginResolver(assignments=assignments, cache={})
    return {
        key: target
        for key in assignments
        if (target := resolver.resolve(key, frozenset())) is not None
    }


def _bound_target(
    node: ast.AST,
    scope: Scope,
    origins: dict[BindingKey, str],
) -> str | None:
    binding = _binding_key(node, scope)
    return origins.get(binding) if binding is not None else None


def _direct_call_targets(
    call: ast.Call,
    imports: ImportBindings,
    shadowed: frozenset[str],
) -> set[str]:
    target = resolve_imported_symbol(call.func, imports, shadowed)
    return {target} if target is not None else set()


def _callable_instance_targets(
    call: ast.Call,
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
    origins: dict[BindingKey, str],
) -> set[str]:
    targets: set[str] = set()
    bound = _bound_target(call.func, scope, origins)
    if bound is not None:
        targets.add(f"{bound}.__call__")
    if isinstance(call.func, ast.Call):
        immediate = resolve_imported_symbol(call.func.func, imports, shadowed)
        if immediate is not None:
            targets.add(f"{immediate}.__call__")
    return targets


def _method_call_targets(
    call: ast.Call,
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
    origins: dict[BindingKey, str],
) -> set[str]:
    if not isinstance(call.func, ast.Attribute):
        return set()
    targets: set[str] = set()
    bound = _bound_target(call.func.value, scope, origins)
    if bound is not None:
        targets.add(f"{bound}.{call.func.attr}")
    if isinstance(call.func.value, ast.Call):
        immediate = resolve_imported_symbol(call.func.value.func, imports, shadowed)
        if immediate is not None:
            targets.add(f"{immediate}.{call.func.attr}")
    return targets


def _call_targets(
    call: ast.Call,
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
    origins: dict[BindingKey, str],
) -> frozenset[str]:
    return frozenset(
        _direct_call_targets(call, imports, shadowed)
        | _callable_instance_targets(call, scope, imports, shadowed, origins)
        | _method_call_targets(call, scope, imports, shadowed, origins)
    )


def _targets_invoked_in_scope(
    scope: Scope,
    imports: ImportBindings,
    shadowed: frozenset[str],
    origins: dict[BindingKey, str],
) -> frozenset[str]:
    targets: set[str] = set()
    for node in walk_scope(scope.node):
        if isinstance(node, ast.Call):
            targets.update(_call_targets(node, scope, imports, shadowed, origins))
    return frozenset(targets)


def invocation_index(tree: ast.Module) -> InvocationIndex:
    imports = import_bindings(tree)
    scopes = module_scopes(tree)
    shadows = {
        scope.key: scope_shadowed_names(scope, imports)
        for scope in scopes
    }
    assignments = _collect_assignments(scopes, imports, shadows)
    origins = _resolved_origins(assignments)
    by_node = {
        id(scope.node): _targets_invoked_in_scope(
            scope,
            imports,
            shadows[scope.key],
            origins,
        )
        for scope in scopes
    }
    return InvocationIndex(
        by_node=by_node,
        module_targets=frozenset(
            target
            for invoked in by_node.values()
            for target in invoked
        ),
    )
