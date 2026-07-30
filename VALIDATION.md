# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6,
uv 0.12.0, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #56 adds a deliberately small, declaration-only capability lifecycle.

- Activation accepts only complete, current evidence for the architecture
  contract, stable surface, normative-property evidence, port contract, and
  CLI-process evidence; each missing item is returned by name.
- Transitions use a conditional declaration write and refuse declarations that
  are not classified as `DECLARATION`, including under a custom ownership
  policy.
- Retirement changes only the declaration status. It neither writes product
  files nor implements deletion, purge, CLI, generation, journals, leases, or
  recovery machinery.
- Stateful proof tests cover refusal, successful activation, retirement's
  product-byte preservation, and reactivation requiring fresh evidence.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 just validate
```

The final canonical `just validate` passed end to end (directly observed exit
code 0):

- root Ruff repair/check was stable across 145 files and the root test suite
  passed with **213 passed, 11 warnings** in 17.62s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- the generated full quality run passed with **277 passed, 8 skipped, 3
  deselected** in 77.18s and **93.94%** coverage (90% required). The hook-repair
  rerun also passed with **277 passed, 8 skipped, 3 deselected** in 77.79s.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess environment and filesystem behavior can differ.
- Lifecycle evidence is supplied by the caller; #56 validates completeness and
  freshness at the declaration boundary rather than independently collecting
  evidence.
- A lifecycle transition does not trigger derived-index generation or expose a
  CLI command. Existing generation can reflect the new declaration state, while
  #58 owns the lifecycle CLI work.
