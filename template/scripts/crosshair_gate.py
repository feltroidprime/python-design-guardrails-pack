#!/usr/bin/env python3
"""Run bounded CrossHair analysis only on explicit pure-core proof targets."""

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType

from scripts.proof_catalog import CatalogError, PropertySpec, load_catalog


@dataclass(frozen=True, slots=True, kw_only=True)
class Budget:
    max_uninteresting_iterations: int
    per_path_timeout: float
    per_condition_timeout: float


BUDGETS = MappingProxyType({
    "fast": Budget(
        max_uninteresting_iterations=4,
        per_path_timeout=0.25,
        per_condition_timeout=1.5,
    ),
    "ci": Budget(
        max_uninteresting_iterations=12,
        per_path_timeout=0.75,
        per_condition_timeout=4.0,
    ),
    "deep": Budget(
        max_uninteresting_iterations=64,
        per_path_timeout=5.0,
        per_condition_timeout=30.0,
    ),
})


def _selected_properties(root: Path, property_ids: tuple[str, ...]) -> tuple[PropertySpec, ...]:
    catalog = load_catalog(root)
    if not property_ids:
        return catalog.properties
    requested = frozenset(property_ids)
    unknown = sorted(requested - catalog.by_id.keys())
    if unknown:
        raise CatalogError(f"Unknown property ID(s): {', '.join(unknown)}")
    return tuple(
        property_spec
        for property_spec in catalog.properties
        if property_spec.property_id in requested
    )


def _crosshair_targets(root: Path, property_ids: tuple[str, ...]) -> tuple[str, ...]:
    targets = {
        target.replace(":", ".", 1)
        for property_spec in _selected_properties(root, property_ids)
        for target in property_spec.crosshair_targets
    }
    return tuple(sorted(targets))


def _command(profile: str, targets: tuple[str, ...]) -> tuple[str, ...]:
    budget = BUDGETS[profile]
    return (
        sys.executable,
        "-m",
        "crosshair",
        "check",
        "--analysis_kind=icontract",
        f"--max_uninteresting_iterations={budget.max_uninteresting_iterations}",
        f"--per_path_timeout={budget.per_path_timeout}",
        f"--per_condition_timeout={budget.per_condition_timeout}",
        *targets,
    )


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in BUDGETS:
        print(
            "Usage: python -m scripts.crosshair_gate {fast|ci|deep} [PROPERTY-ID ...]",
            file=sys.stderr,
        )
        return 2
    profile = argv[0]
    property_ids = tuple(argv[1:])
    root = Path(__file__).resolve().parents[1]
    try:
        targets = _crosshair_targets(root, property_ids)
    except CatalogError as error:
        print(f"Cannot select CrossHair targets: {error}", file=sys.stderr)
        return 2
    if not targets:
        suffix = f" for {', '.join(property_ids)}" if property_ids else ""
        print(f"CrossHair: no explicit targets{suffix}.")
        return 0
    if find_spec("crosshair") is None:
        print(
            "The 'crosshair' module was not found. Run `uv sync --all-groups` "
            "before the proof gate.",
            file=sys.stderr,
        )
        return 127
    print(f"CrossHair ({profile}): {', '.join(targets)}", flush=True)
    completed = subprocess.run(_command(profile, targets), cwd=root, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
