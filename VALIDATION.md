# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6,
uv 0.12.0, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #57 makes the product CLI catalog consume the generated active-capability
index without runtime module discovery.

- The catalog imports `CLI_CATALOGS`, merges declared catalogs deterministically,
  and keeps the existing closed dispatcher intact.
- During this deletion-first transition, a capability can claim only the legacy
  `add` or `list` descriptor; duplicate claims fail closed and `capabilities`
  remains non-replaceable.
- An integration test writes an active `alpha` declaration and its local catalog,
  regenerates the derived index, verifies that the published `add` descriptor
  came from `alpha`, and invokes the retained closed-dispatch command.
- The empty CLI and composition index seeds now match compiler output
  (`tuple[object, ...]`), so zero-capability regeneration is byte-stable.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 just validate
```

The final canonical `just validate` passed end to end:

- root Ruff repair/check was stable across 145 files and the root test suite
  passed with **213 passed, 11 warnings** in 17.61s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- the generated full quality run passed with **279 passed, 8 skipped, 3
  deselected** in 77.92s and **93.10%** coverage (90% required). The hook-repair
  rerun also passed with **279 passed, 8 skipped, 3 deselected** in 77.51s.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess environment and filesystem behavior can differ.
- This leaf deliberately composes existing legacy command descriptors rather
  than inventing generic capability command execution. A future arbitrary
  product-command runtime needs its own command/handler contract and dispatch
  design.
