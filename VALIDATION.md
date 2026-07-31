# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #72 adds one focused multi-capability composition fixture without
changing the generated template or shared recursive harness.

- The generated repository's real CLI creates provider `alpha` and consumer
  `beta`, and their existing declaration fields name two tiny public factories.
- With both capabilities active, an outer bootstrap imports only the derived
  `COMPOSITION` tuple and injects the provider callable into the consumer-owned
  callable port for a real quote scenario.
- An AST assertion rejects every provider import from all consumer sources,
  while a deliberate provider-domain import proves the canonical capability
  validator emits CAP003.
- Retiring the provider removes its factory from `COMPOSITION`, leaves the
  consumer factory importable, and preserves every consumer PRODUCT byte using
  the recursive harness's canonical product-file scope.

## Commands and actual results

```bash
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q tests/recursive/test_shape_composition.py
just check
just validate
```

The initial focused test failed as intended before its two fixture assets
existed. The final focused test passed **1 test** with one expected Copier
dirty-template warning in 6.70 seconds. Root Ruff reported **154 files already
formatted** and no lint violations.

The canonical `just validate` command passed end to end:

- root Ruff repair/check was stable across 154 files, and the root suite passed
  **244 tests** with 21 dirty-template warnings in 553.82 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- the three generated gate executions each passed **127 tests, 1 skipped,
  3 deselected**, in 32.73, 35.66, and 36.67 seconds, with **95.65% coverage**
  (90% required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The successful canonical root suite took 553.82 seconds, within the
  documented ten-minute warm-cache budget but with little headroom.
- The generated composition index intentionally exposes a deterministic tuple
  of active factories; dependency ordering and invocation remain the outer
  bootstrap's responsibility.
- The CLI has no factory option, so this test sets the existing factory field
  only in its throwaway declarations after real plan/apply creation.
- The remaining agent-workflow case is owned by issue #73.
