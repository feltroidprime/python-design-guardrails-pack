# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #46 of epic #44 certifies the repository-generation filesystem port with
its deterministic in-memory adapter. It builds on the port and shared
behavioral contract from #45.

- `RepositoryPort` now owns canonical repository snapshots, conditional writes,
  directory creation, and opaque durable transaction journals.
- `MemoryRepository` uses a lock-protected content store, normalizes locations,
  rejects configured escape locations, preserves CAS conflicts, and represents
  recoverable opaque transaction journals. Its snapshots derive capability
  declarations and content digests from in-memory state.
- All ten shared contract behaviors execute against fresh memory state, with a
  separate certification check ensuring the collected shared-case count equals
  the declared contract-case count.

## Commands and actual results

```bash
just test
# 215 passed, 12 warnings in 26.40s

uv run pytest -q -m contract tests/repoctl/contract/test_memory_repository.py
# 12 passed, 2 deselected in 0.46s

just validate
```

The final canonical `just validate` passed end to end:

- root Ruff repair/check was stable across 126 files; root tests: **215
  passed, 12 warnings** in 31.51s;
- generated repository bootstrap, formatting, linting, BasedPyright (**0
  errors, 0 warnings**), ownership (**174 paths**), architecture, docs, proof,
  symbolic, and import-contract gates all passed;
- generated tests collected the new contract as
  `tests/repoctl/contract/test_memory_repository.py ..............` and
  completed **217 passed, 8 skipped, 3 deselected** in 20.59s with **93.94%**
  coverage;
- the generated contract-only selection completed **12 passed, 2 deselected**;
  its local test configuration omits sample-application coverage reporting
  only for that isolated port-contract command;
- the missing-hook repair, tracked-syntax fault injection, clean/dirty doctor
  probes, and linked-worktree pre-commit/pre-push checks passed;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 58.34s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- The local-filesystem implementation remains pending in issue #47. The
  in-memory fake deliberately models symlink escapes through configured
  locations; #47 will additionally certify real filesystem symlink handling.
- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised.
