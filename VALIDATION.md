# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #50 of epic #44 adds the application-owned, stale-safe capability-plan
apply protocol.

- `apply(plan, repository)` validates immutable plan identity and generator
  version, observes the current snapshot and journal before writing, rejects
  stale plans with the required recovery instruction, and records each write
  through the #49 transaction journal.
- Reapplying a completed plan returns `already_applied` without another write.
  Interrupted or result-mismatched work is recovered and reported as requiring
  a fresh plan rather than silently replanned.
- A present path classified as product is refused before compare-and-swap can
  write it, even when a forged plan's precondition matches its current bytes.
- The proof catalog owns state-machine evidence for idempotence, stale-plan
  rejection, and product-byte preservation. The generated proof recipes now
  discover the complete `verification/` tree, including the `repoctl` capsule.

## Commands and actual results

```bash
just validate
```

The final canonical `just validate` passed end to end (directly observed exit
code 0):

- root Ruff repair/check was stable across 135 files; root tests: **215
  passed** in 27.99s;
- template cleanliness, fresh instantiation, generated bootstrap and quality
  gates, tracked-syntax and dirty-doctor fault probes, and linked-worktree
  pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 62.33s**.

Additional downstream checks run against a freshly rendered repository:

```bash
just prove
just prove-one REPOCTL::APPLY-IDEMPOTENT
just prove-one REPOCTL::STALE-PLAN-REJECTED
just prove-one REPOCTL::PRODUCT-BYTES-PRESERVED
uv run pytest -q
```

- `just prove` passed **37** proof tests (24 deselected); each new property
  appears in `proof_guard --report` with `hypothesis-stateful` evidence.
- Each `prove-one` command passed its selected property test plus falsifier
  (**2 passed**, 59 deselected).
- The direct generated test suite completed **238 passed, 8 skipped, 3
  deselected** in 19.57s with **93.94%** coverage.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their symlink permissions and directory fsync behavior differ.
- The apply protocol is deliberately fail-closed after an interrupted journal:
  it preserves the durable evidence and tells the caller to re-plan instead of
  attempting an implicit rollback or regeneration.
