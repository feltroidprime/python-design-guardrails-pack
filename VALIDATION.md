# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #48 of epic #44 adds the read-only repository-control queries after the
repository port (#45), in-memory adapter (#46), and local adapter (#47). This
record also covers a post-close repair to its generated import layout.

- `python -m repoctl capabilities` pages declared product capability modules in
  stable name order and returns the product CLI's versioned JSON envelope.
- `python -m repoctl status` reports the repository schema, package, and draft,
  active, and retired product-capability counts. Its active count is derived by
  the canonical `derived-index-v1` compilation rather than a duplicate filter.
- The catalog is built with the product CLI's actual `CommandSpec`,
  `QueryPolicy`, argument, outcome, and protocol types; it introduces only the
  control-plane command identities.
- Both commands reach state solely through `RepositoryPort.snapshot()`. Their
  integration test proves no repository-state change, bounded continuation,
  structured invalid-limit diagnostics, and control/product protocol type
  identity.
- The system capability's public API lazily resolves Jinja-rendered control
  modules, keeping the pack's unrendered template importable while preserving
  the generated repository's public API boundary.
- Generated-package imports and `repoctl` imports now use explicit isort split
  boundaries. That keeps Ruff ordering independent of the consumer-selected
  package name, including Copier update round trips.

## Commands and actual results

```bash
PACK_RUN_DOWNSTREAM_GATE=1 uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with pytest-xdist==3.8.0 \
  --with copier==9.17.0 --with 'icontract>=2.7.3' \
  pytest -q tests/test_update_roundtrip.py::test_previous_release_updates_cleanly_to_current_ref
# 1 passed in 55.96s

just validate
```

The final canonical `just validate` passed end to end:

- root Ruff repair/check was stable across 131 files; root tests: **215
  passed, 12 warnings** in 25.40s;
- generated repository bootstrap, formatting, linting, BasedPyright (**0
  errors, 0 warnings**), ownership (**183 paths**), architecture, docs, proof,
  symbolic, and import-contract gates all passed;
- generated tests completed **238 passed, 8 skipped, 3 deselected** in 22.99s
  with **93.94%** coverage;
- the missing-hook repair, tracked-syntax fault injection, clean/dirty doctor
  probes, and linked-worktree pre-commit/pre-push checks passed;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 60.56s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their symlink permissions and directory fsync behavior differ.
- `repoctl` is a root-level generated package, so ordinary use is from the
  generated repository root. The isolated integration test sets `PYTHONPATH`
  to that root only to exercise an independent temporary repository directory.
