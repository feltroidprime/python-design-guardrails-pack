# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #49 of epic #44 adds the application-owned
`transaction-journal-v1` contract over the repository port.

- Each exact capability plan receives the stable `apply:<plan-id>` transaction
  identifier and a canonical JSON header containing its plan ID and base-state
  digest.
- Operation records carry a deterministic sequence, kind, path, precondition,
  and content digest. The terminal record binds the plan's result-state digest
  before the transaction is marked complete.
- Inspection rejects mismatched or out-of-order records, reports incomplete
  progress with the last recorded target, and preserves recovery classification
  through `RepositoryPort.recover_transaction()`.
- Replaying a completed plan is a no-op. The unit suite compares the complete
  stored in-memory snapshot and transaction bytes before and after replay.
- The journal module has no direct filesystem dependency; its AST evidence
  permits only the transaction methods on `RepositoryPort`.

## Commands and actual results

```bash
just validate
```

The final canonical `just validate` passed end to end:

- root Ruff repair/check was stable across 131 files; root tests: **215
  passed** in 23.61s;
- generated repository bootstrap, formatting, linting, BasedPyright (**0
  errors, 0 warnings**), ownership (**183 paths**), architecture, docs, proof,
  symbolic, and import-contract gates all passed;
- generated tests completed **238 passed, 8 skipped, 3 deselected** in 21.52s
  with **93.94%** coverage;
- the missing-hook repair, tracked-syntax fault injection, clean/dirty doctor
  probes, and linked-worktree pre-commit/pre-push checks passed;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 60.23s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their symlink permissions and directory fsync behavior differ.
- This leaf journals protocol state only. The #50 apply use case must call it
  around real writes and enforce the stale-plan and existing-product-file
  policies from the frozen specification.
