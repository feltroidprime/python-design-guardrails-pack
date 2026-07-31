# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #68 certifies a pure library capability without adding an application
effect, adapter implementation, production template change, or harness change.

- The existing recursive harness creates, activates, proves, gates, retires,
  and preserves the capability through the real repoctl lifecycle.
- The fixture supplies one deterministic, I/O-free, icontract-checked domain
  function, an independent specification, and one stable `api.py` surface.
- External Python imports of the capability resolve only to `api.py`.
  Generator-seeded `__init__.py` package markers are the only Python files
  under its application and adapter directories.
- An unfiltered detached `scripts.crosshair_gate fast` run names the fixture's
  pure target, so the symbolic canary alone cannot satisfy the assertion.
- The generated repository contains no `tests/fixtures/shapes/` path.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q -x tests/recursive/test_shape_pure_library.py
PYTHONDONTWRITEBYTECODE=1 just check
PYTHONDONTWRITEBYTECODE=1 just validate
```

The TDD red run failed at the intended missing fixture asset after 77.46
seconds. After adding the five fixture assets, the focused #68 test passed
**1 test** with one dirty-template warning in 239.52 seconds. Root Ruff
reported **151 files already formatted** and no lint violations.

The canonical command passed end to end:

- root Ruff repair/check was stable across 151 files, and the root suite passed
  **226 tests** with 19 dirty-template warnings in 540.54 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- both generated gates passed **127 tests, 1 skipped, 3 deselected**, first in
  43.80 seconds and then in 45.86 seconds, with **95.65% coverage** (90%
  required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The successful root suite took 540.54 seconds, within the documented
  ten-minute warm-cache budget but with limited headroom for later recursive
  shape fixtures.
- The fixture proves purity structurally and symbolically within the generated
  repository. It does not claim that arbitrary consumers outside the checked
  Python source roots obey the API boundary.
- The remaining stateful-workflow, composition, mutation,
  update-preservation, and workflow-documentation cases are owned by issues
  #69–#73.
