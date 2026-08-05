# Architecture

## Boundaries

A project holds two kinds of code, and one predicate divides them.

```text
pack/                    the Pack-owned Surface: policy, guards, the gate
src/<package>/           the product
  _foundation/           pack-owned: the router, the envelopes, the outcomes
  cli.py                 user-owned: a two-line entry point
  composition.py         user-owned: the CAPABILITIES tuple
  <capability>/          user-owned: api, domain, application, adapters, tests
```

A Product Capability is one directory directly under the package. Its layers
point inward: `api`, `domain`, `application`, `adapters`. No document here
names the package, because every file under `pack/` is byte-identical in every
project.

## Ownership

Two surfaces, and one predicate states both. Pack-owned is the `pack/`
directory, plus `_`-prefixed names and `py.typed` inside the package.
User-owned is everything else. `pack/scripts/ownership.py` holds the predicate,
and no file holds a list of ownership roots. ADR-0008 records the decision.

An update of the pack replaces whole pack-owned files, and it writes no
user-owned file. Four user-owned entry points at the root are thin shims into
`pack/`. An update reports a suggested change to each one and never writes it.

## Stable seams

- `pack/architecture.toml` is the only declaration of limits, conventions and
  domain purity. It names no package and no ownership root.
- `_foundation/router.py` is the one command seam. It imports exactly one
  user-owned module, the composition root, and reads its `CAPABILITIES` tuple.
- The `api.py` of a capability is that capability's public surface. Reach a
  capability through it, and never through its internals.
- `pack/proof/policy.toml` configures proof discovery, and each catalog beside
  it declares one set of laws.
- `pack/configs/` is a path ABI: a release can change the content of a config
  file, and never its name or its location.

## Fitness functions

- `pack/scripts/architecture_guard.py` carries the structure and source rules.
- `pack/scripts/import_contracts.py` runs the six `import-linter` contracts of
  `pack/configs/importlinter.ini` over every discovered capability.
- `pack/scripts/cli_surface.py` checks every command surface against `CLI001`
  to `CLI004`, composed or not.
- `pack/scripts/docs_guard.py` keeps this documentation set true.
- `pack/scripts/proof_guard.py`, Hypothesis and `pack/scripts/crosshair_gate.py`
  keep the proof chain closed and refute the symbolic canary.
- `pack/scripts/manifest_guard.py` fails a stale record of the Pack-owned
  Surface at commit time.
- Ruff, BasedPyright and pytest read their policy from `pack/configs/`.

Twelve hooks run as one gate: `prek run --all-files -c pack/configs/prek.toml`.
`just check` and CI run that one command, so a local run and a CI run cannot
disagree. No coverage assertion exists anywhere in the tree.
