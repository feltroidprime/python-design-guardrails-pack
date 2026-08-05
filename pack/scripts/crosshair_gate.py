#!/usr/bin/env python3
"""Run bounded CrossHair analysis only on explicit pure-core proof targets.

Every target is analysed on its own and reported by name, and one deliberately
false canary contract is analysed alongside them. A symbolic run that cannot
construct the domain types reports nothing and exits zero, so the canary is what
separates "searched and found no counterexample" from "searched nothing".
"""

from dataclasses import dataclass
from importlib.util import find_spec
import os
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType

from scripts.proof_catalog import CatalogError, ProofCatalog, PropertySpec, load_catalog

CANARY_TARGET = "verification.harness.symbolic_canary:refutable_echo"
CANARY_OWNER = "SYMBOLIC-CANARY"
REFUTED_MARKER = ": error: "
CONFIRMED_MARKER = "Confirmed over all paths"


@dataclass(frozen=True, slots=True, kw_only=True)
class Budget:
    max_uninteresting_iterations: int
    per_path_timeout: float
    per_condition_timeout: float


BUDGETS = MappingProxyType(
    {
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
    }
)
CANARY_MINIMUM_BUDGET = Budget(
    max_uninteresting_iterations=16,
    per_path_timeout=1.5,
    per_condition_timeout=8.0,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolicTarget:
    """One analysed symbol and the property whose contract it carries."""

    owner: str
    target: str
    must_refute: bool

    @property
    def dotted(self) -> str:
        return self.target.replace(":", ".", 1)


@dataclass(frozen=True, slots=True, kw_only=True)
class TargetOutcome:
    """What one bounded symbolic search established about one target."""

    target: SymbolicTarget
    output: str
    refuted: bool
    confirmed: bool
    exit_code: int

    @property
    def satisfied(self) -> bool:
        if self.target.must_refute:
            return self.refuted
        return not self.refuted and self.exit_code == 0

    @property
    def status(self) -> str:
        if self.refuted:
            return "refuted (expected)" if self.target.must_refute else "counterexample found"
        if self.exit_code != 0:
            return f"analysis failed (exit {self.exit_code})"
        if self.confirmed:
            return "confirmed over all paths"
        if self.target.must_refute:
            return "NOT refuted: the symbolic layer cannot reason about the domain types"
        return "searched, no counterexample (bounded)"


def _selected_properties(
    catalog: ProofCatalog,
    property_ids: tuple[str, ...],
) -> tuple[PropertySpec, ...]:
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


def _symbolic_targets(
    catalog: ProofCatalog,
    property_ids: tuple[str, ...],
) -> tuple[SymbolicTarget, ...]:
    owners: dict[str, set[str]] = {}
    for property_spec in _selected_properties(catalog, property_ids):
        for target in property_spec.crosshair_targets:
            owners.setdefault(target, set()).add(property_spec.property_id)
    if not owners:
        return ()
    proof_targets = tuple(
        SymbolicTarget(owner=", ".join(sorted(ids)), target=target, must_refute=False)
        for target, ids in sorted(owners.items())
    )
    canary = SymbolicTarget(owner=CANARY_OWNER, target=CANARY_TARGET, must_refute=True)
    return (*proof_targets, canary)


def _command(profile: str, target: SymbolicTarget) -> tuple[str, ...]:
    profile_budget = BUDGETS[profile]
    budget = (
        Budget(
            max_uninteresting_iterations=max(
                profile_budget.max_uninteresting_iterations,
                CANARY_MINIMUM_BUDGET.max_uninteresting_iterations,
            ),
            per_path_timeout=max(
                profile_budget.per_path_timeout,
                CANARY_MINIMUM_BUDGET.per_path_timeout,
            ),
            per_condition_timeout=max(
                profile_budget.per_condition_timeout,
                CANARY_MINIMUM_BUDGET.per_condition_timeout,
            ),
        )
        if target.must_refute
        else profile_budget
    )
    return (
        sys.executable,
        "-m",
        "crosshair",
        "check",
        "--report_all",
        "--analysis_kind=icontract",
        f"--max_uninteresting_iterations={budget.max_uninteresting_iterations}",
        f"--per_path_timeout={budget.per_path_timeout}",
        f"--per_condition_timeout={budget.per_condition_timeout}",
        target.dotted,
    )


def _source_environment(source_roots: tuple[Path, ...]) -> dict[str, str]:
    environment = dict(os.environ)
    declared = tuple(str(path) for path in source_roots)
    inherited = environment.get("PYTHONPATH", "")
    entries = (*declared, inherited) if inherited else declared
    environment["PYTHONPATH"] = os.pathsep.join(entries)
    return environment


def _analyse(
    root: Path,
    profile: str,
    target: SymbolicTarget,
    source_roots: tuple[Path, ...],
) -> TargetOutcome:
    completed = subprocess.run(
        _command(profile, target),
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=_source_environment(source_roots),
    )
    output = completed.stdout + completed.stderr
    return TargetOutcome(
        target=target,
        output=output,
        refuted=REFUTED_MARKER in output,
        confirmed=CONFIRMED_MARKER in output,
        exit_code=completed.returncode,
    )


def _report_failure(outcome: TargetOutcome) -> None:
    print(f"\nPROPERTY[{outcome.target.owner}] {outcome.target.target}", file=sys.stderr)
    if outcome.target.must_refute:
        print(
            (
                "The symbolic canary was not refuted, so CrossHair proved nothing about "
                "the real targets in this run. Restore symbolic constructibility of the "
                "domain types before trusting any result above."
            ),
            file=sys.stderr,
        )
    detail = outcome.output.strip()
    if detail:
        print(detail, file=sys.stderr)


def _run_targets(
    root: Path,
    profile: str,
    targets: tuple[SymbolicTarget, ...],
    source_roots: tuple[Path, ...],
) -> int:
    print(f"CrossHair ({profile}): {len(targets)} target(s)", flush=True)
    outcomes: list[TargetOutcome] = []
    for target in targets:
        outcome = _analyse(root, profile, target, source_roots)
        print(f"  {target.owner} | {target.target} | {outcome.status}", flush=True)
        outcomes.append(outcome)
    failed = [outcome for outcome in outcomes if not outcome.satisfied]
    for outcome in failed:
        _report_failure(outcome)
    if failed:
        print(f"\n{len(failed)} symbolic target(s) failed.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in BUDGETS:
        print(
            "Usage: python -m scripts.crosshair_gate {fast|ci|deep} [PROPERTY-ID ...]",
            file=sys.stderr,
        )
        return 2
    profile = argv[0]
    property_ids = tuple(argv[1:])
    root = Path(__file__).resolve().parents[2]
    try:
        catalog = load_catalog(root)
        targets = _symbolic_targets(catalog, property_ids)
    except CatalogError as error:
        print(f"Cannot select CrossHair targets: {error}", file=sys.stderr)
        return 2
    if not targets:
        suffix = f" for {', '.join(property_ids)}" if property_ids else ""
        print(f"CrossHair: no explicit targets{suffix}.")
        return 0
    if find_spec("crosshair") is None:
        print(
            (
                "The 'crosshair' module was not found. Run `uv sync --all-groups` "
                "before the proof gate."
            ),
            file=sys.stderr,
        )
        return 127
    return _run_targets(root, profile, targets, catalog.policy.source_roots)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
