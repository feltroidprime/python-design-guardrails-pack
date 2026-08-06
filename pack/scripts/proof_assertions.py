"""Discover literal property links carried by proof assertion helpers.

This is machinery for `proof_evidence_rules.py`. It emits no PROOF code.
"""

import ast

from scripts.proof_ast import dotted_name

PROOF_HELPERS = frozenset({"assert_property", "assert_falsifies", "assert_rejected"})


def _helper_property_id(call: ast.Call, name: str) -> tuple[str | None, str | None]:
    keyword = next((item for item in call.keywords if item.arg == "property_id"), None)
    if keyword is None:
        return None, f"{name}@{call.lineno}:missing-property_id"
    value = keyword.value
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return None, f"{name}@{call.lineno}:dynamic-property_id"
    return value.value, None


def helper_calls(node: ast.AST) -> tuple[frozenset[str], tuple[str, ...], tuple[str, ...]]:
    names: set[str] = set()
    ids: list[str] = []
    dynamic: list[str] = []
    for candidate in ast.walk(node):
        if not isinstance(candidate, ast.Call):
            continue
        name = dotted_name(candidate.func).split(".")[-1]
        if name not in PROOF_HELPERS:
            continue
        names.add(name)
        property_id, defect = _helper_property_id(candidate, name)
        if property_id is not None:
            ids.append(property_id)
        if defect is not None:
            dynamic.append(defect)
    return frozenset(names), tuple(ids), tuple(dynamic)
