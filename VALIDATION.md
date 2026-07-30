# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #45 of epic #44 establishes the repository-generation filesystem port
and its reusable behavioral contract.

- `RepositoryPort` now owns canonical repository snapshots, conditional writes,
  directory creation, and opaque durable transaction journals.
- The contract covers absent writes, compare-and-swap success/conflict,
  directory creation, normalized paths, symlink escape rejection, interrupted
  transactions, recovery, and read-after-write consistency.  Before an adapter
  is certified it remains visibly collected as one passing surface-coverage
  check and one intentional empty-parameter skip.
- The repository-generation application guard now permits only its closed pure
  import allowlist while continuing to reject ambient-effect imports and calls;
  the generated mutation canaries exercise `os`/`open` and
  `shutil.copyfile` against the new port module.

## Commands and actual results

```bash
just test
# 215 passed, 12 warnings in 24.99s

just validate
```

The final canonical `just validate` passed end to end:

- root Ruff repair/check was stable across 123 files; root tests: **215
  passed, 12 warnings** in 23.62s;
- generated repository bootstrap, formatting, linting, BasedPyright (**0
  errors, 0 warnings**), ownership (**171 paths**), architecture, docs, proof,
  symbolic, and import-contract gates all passed;
- generated tests collected the new contract as
  `tests/repoctl/contract/test_repository_port_contract.py .s` and completed
  **203 passed, 8 skipped, 3 deselected** in 22.19s with **93.94%** coverage;
- the missing-hook repair, tracked-syntax fault injection, clean/dirty doctor
  probes, and linked-worktree pre-commit/pre-push checks passed;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 58.26s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- The in-memory and local-filesystem implementations are intentionally pending
  in issues #46 and #47; the contract is currently collected but has no live
  adapter parameterization.
- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised.
