# Architecture

## N0 boundaries

N0 contains one template-maintained system capability:

```text
repoctl.modules.repository_generation
  domain ← application ← adapters
```

The package contains only its `_foundation` boundary. No document here names
the package, because every file under `pack/` is byte-identical in every
project.

## Ownership

Two zones, and one predicate states them. Pack-owned is the `pack/` directory,
plus `_`-prefixed names and `py.typed` inside the package. User-owned is
everything else. `pack/scripts/ownership.py` holds the predicate, and no file
holds a list of ownership roots.

A future product capability is declared and materialized by repository control.
It owns its own domain, application, adapters, API, proof catalog, and derived
registration; N0 does not guess any of them.

## Stable seams

- `pack/architecture.toml` is the sole limit, convention, and domain-purity
  declaration. It declares no package name and no ownership root.
- `repoctl.modules.repository_generation.api` is the public surface of the
  shipped capability.
- `pack/proof/policy.toml` discovers the common proof system;
  `pack/proof/ownership.toml` owns the ownership law.

## Fitness functions

- `pack/scripts/architecture_guard.py` enforces structure and source rules.
- `pack/scripts/capability_validator.py` applies CAP001–CAP003 to repository control
  and future capabilities alike.
- `scripts/proof_guard.py`, Hypothesis, and `scripts/crosshair_gate.py` keep
  the repository-control proof chain closed and refute the symbolic canary.
- BasedPyright, Ruff, pytest, and the 90% coverage floor remain part of
  `just check`.
