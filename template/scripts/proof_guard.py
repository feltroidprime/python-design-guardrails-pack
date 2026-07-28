#!/usr/bin/env python3
"""Enforce a closed property-to-contract-to-evidence chain."""

import sys
from pathlib import Path

from scripts.proof_catalog import CatalogError, ProofCatalog, load_catalog
from scripts.proof_discovery import (
    DiscoveryError,
    discover_behavior_targets,
    discover_tests,
)
from scripts.proof_evidence_rules import evidence_coverage_violations
from scripts.proof_guard_model import Violation, violation
from scripts.proof_oracle_rules import oracle_violations
from scripts.proof_target_rules import (
    build_target_map,
    closure_violations,
    property_target_violations,
)


def check(root: Path) -> tuple[ProofCatalog | None, tuple[Violation, ...]]:
    try:
        catalog = load_catalog(root)
        behavior_targets = discover_behavior_targets(catalog.policy)
        target_map = build_target_map(catalog)
        tests = tuple(
            proof_test
            for test_root in catalog.policy.test_roots
            for proof_test in discover_tests(test_root)
        )
    except (CatalogError, DiscoveryError, OSError, SyntaxError) as error:
        return None, (
            violation(root / "proof" / "policy.toml", 1, "PROOF000", str(error)),
        )
    violations = [
        *closure_violations(catalog, behavior_targets),
        *property_target_violations(catalog, target_map),
        *oracle_violations(catalog),
        *evidence_coverage_violations(catalog, tests),
    ]
    return catalog, tuple(
        sorted(
            violations,
            key=lambda item: (str(item.path), item.line, item.code, item.message),
        )
    )


def _report(catalog: ProofCatalog) -> None:
    print("ID | kind | assumptions | evidence | targets")
    print("---|---|---:|---|---")
    for property_spec in catalog.properties:
        row = (
            f"{property_spec.property_id} | {property_spec.kind} | "
            f"{len(property_spec.assumptions)} | "
            f"{', '.join(sorted(property_spec.evidence))} | "
            f"{', '.join(property_spec.targets)}"
        )
        print(row)


def main(argv: list[str]) -> int:
    if argv not in ([], ["--report"]):
        print("Usage: python -m scripts.proof_guard [--report]", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    catalog, violations = check(root)
    if violations:
        for violation in violations:
            print(violation.render(root))
        print(f"\n{len(violations)} proof-contract violation(s).", file=sys.stderr)
        return 1
    if catalog is None:
        raise AssertionError("Successful proof validation must return its catalog")
    if argv == ["--report"]:
        _report(catalog)
    else:
        crosshair_count = sum(
            len(property_spec.crosshair_targets) for property_spec in catalog.properties
        )
        summary = (
            f"Proof contract passed: {len(catalog.properties)} properties, "
            f"{crosshair_count} CrossHair target(s)."
        )
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
