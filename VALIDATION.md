# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #66 certifies a capability-owned command boundary without reviving the
deleted package-root product CLI.

- The unchanged recursive harness creates the capability through the real
  control plane; the fixture then uses another detached plan/apply pair to
  declare its `cli` inbound seam without patching the declaration.
- The capability owns a local command catalog and
  `python -m recursive_project.modules.alpha probe` entry point. Its retained
  process case closes stdin and passes after retirement.
- Activation without `--cli-process-evidence` is refused with the structured
  `missing_evidence` outcome; the harness's complete evidence activates it.
- The generated repository's existing exactness check observes both ACTIVE and
  RETIRED gates, including the intentionally empty global CLI catalog, while
  the recursive harness proves PRODUCT bytes remain unchanged.
- No package-root CLI, generated-index format, production template, or harness
  behavior changed.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q tests/recursive/test_shape_cli_capability.py
PYTHONDONTWRITEBYTECODE=1 just check
PYTHONDONTWRITEBYTECODE=1 just validate
```

The focused #66 test passed **1 test** with one dirty-template warning in
189.69 seconds. Root Ruff reported **148 files already formatted** and no lint
violations.

The canonical command passed end to end:

- root Ruff repair/check was stable across 148 files, and the root suite passed
  **224 tests** with 17 dirty-template warnings in 292.54 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- generated tests passed **127 passed, 1 skipped, 3 deselected** with **95.65%
  coverage** (90% required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess, filesystem, and timing behavior can differ.
- This fixture certifies its successful capability-local `probe` process and
  required activation evidence. It deliberately makes no package-root command,
  global product-catalog, or broader command error-protocol claim.
- The remaining application-shape, mutation, composition, update-preservation,
  and workflow-documentation cases are owned by issues #67–#73.
