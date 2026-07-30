# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #47 of epic #44 certifies the repository-generation filesystem port with
its real local-filesystem adapter. It builds on the in-memory certification
from #46 and the shared behavioral contract from #45.

- `RepositoryPort` now owns canonical repository snapshots, conditional writes,
  directory creation, and opaque durable transaction journals.
- `LocalRepository` confines paths to a real repository root, writes staged
  files by fsyncing a same-directory temporary file before replacement, and
  fsyncs journal writes. Its append-only journals never report a truncated
  record as complete, and transaction files are excluded from snapshots.
- All ten shared contract behaviors execute against a fresh real temporary
  directory. The certification compares its collected shared-case count with
  the in-memory implementation, creates an escaping real symlink, and
  truncates a staged journal record.

## Commands and actual results

```bash
just test
# 215 passed, 12 warnings in 25.15s

uv run pytest -q -m contract tests/repoctl/contract/test_local_repository.py
# 13 passed in 0.82s

just validate
```

The final canonical `just validate` passed end to end:

- root Ruff repair/check was stable across 128 files; root tests: **215
  passed, 12 warnings** in 26.87s;
- generated repository bootstrap, formatting, linting, BasedPyright (**0
  errors, 0 warnings**), ownership (**176 paths**), architecture, docs, proof,
  symbolic, and import-contract gates all passed;
- generated tests collected the new contract as
  `tests/repoctl/contract/test_local_repository.py .............` and
  completed **230 passed, 8 skipped, 3 deselected** in 21.26s with **93.94%**
  coverage;
- the generated contract-only selection completed **13 passed**;
  its local test configuration omits sample-application coverage reporting
  only for that isolated port-contract command;
- the missing-hook repair, tracked-syntax fault injection, clean/dirty doctor
  probes, and linked-worktree pre-commit/pre-push checks passed;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 58.13s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation and the real-symlink test ran on Linux x86_64 only. macOS
  and Windows remain unexercised; in particular, local symlink permissions and
  directory fsync support differ by platform.
