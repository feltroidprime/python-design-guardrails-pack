# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6,
uv 0.12.0, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #58 exposes the guarded control-plane lifecycle and reporting operations
on the generated `repoctl` CLI.

- `capability activate`, `capability retire`, `generate`, and `proof-report`
  are declared in the closed control-command catalog and listed by
  `repoctl capabilities`.
- The existing mutation boundary owns all control mutations; the duplicate
  lifecycle CLI adapter was removed. Focused saved-plan decoding and output
  formatting seams keep that boundary below the 650-line architecture ceiling.
- Refusal language for lifecycle and proof-contract outcomes lives in the
  canonical CLI outcome module.
- The detached-process case catalog supplies closed-stdin evidence for every
  control command and fails closed if a catalog command lacks such a case.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 just validate
```

The final canonical `just validate` passed end to end:

- root Ruff repair/check was stable across 145 files and the root test suite
  passed with **213 passed, 11 warnings** in 19.99s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- the generated full quality run passed with **283 passed, 8 skipped, 3
  deselected** in 81.39s and **93.10%** coverage (90% required). The hook-repair
  rerun also passed with **283 passed, 8 skipped, 3 deselected** in 80.78s.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess environment and filesystem behavior can differ.
- `proof-report` reports the existing property/evidence matrix. It is not a new
  proof-index format, and it still fails closed when the proof contract does not
  validate.
