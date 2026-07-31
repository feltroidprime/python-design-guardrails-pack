# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #67 certifies an outbound integration boundary without adding a live
network dependency or changing the recursive harness.

- Detached repoctl plan/apply declares alpha's `transport` outbound seam; the
  fixture never patches its declaration.
- An application-owned port has a fake adapter and an injected-transport real
  adapter. One explicit balanced case table runs the same independent
  behavioral specification against both.
- The real adapter translates an injected `OSError` into the capability-owned
  `IntegrationUnavailableError`; the low-level type remains only as the chained
  cause.
- Before the shared contract file is installed, detached activation without
  `--port-contract` is refused with `missing_evidence` naming `port_contract`
  and alpha remains DRAFT. The unchanged harness then supplies complete
  evidence, reaches ACTIVE, proves the property, and completes retirement.
- Repeated process, JSON-selection, and asset-install mechanics used by the CLI
  and external-integration shapes now live in one small test-support module.
  No production template or harness behavior changed.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q tests/recursive/test_shape_external_integration.py
PYTHONDONTWRITEBYTECODE=1 just check
PYTHONDONTWRITEBYTECODE=1 just validate
```

The focused #67 test passed **1 test** with one dirty-template warning in
195.35 seconds. Root Ruff reported **150 files already formatted** and no lint
violations.

The first canonical attempt reached **224 passed** before an existing
workspace-member generation test failed while Copier removed a temporary clone:
`OSError: [Errno 39] Directory not empty: .../.git`. That exact test then passed
serially (**1 passed**, one warning, 2.63 seconds). A second canonical attempt
showed an early failure marker and was manually interrupted before pytest
printed its traceback, so no cause is claimed for it. The fail-fast diagnostic
root suite subsequently passed **225 tests** with 18 warnings in 600.36 seconds.

The final unmodified canonical command passed end to end:

- root Ruff repair/check was stable across 150 files, and the root suite passed
  **225 tests** with 18 dirty-template warnings in 662.91 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- both generated gates passed **127 tests, 1 skipped, 3 deselected**, first in
  57.96 seconds and then in 52.01 seconds, with **95.65% coverage** (90%
  required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The successful root suite took 662.91 seconds, 62.91 seconds beyond the
  documented ten-minute warm-cache budget. The check passed, but concurrent
  recursive generated gates now create measurable CPU contention that later
  shape issues should avoid multiplying.
- The real adapter is certified with deterministic injected transports, not a
  live third-party service. Activation still relies on explicit evidence flags;
  repoctl does not discover contract files automatically.
- The remaining application-shape, mutation, composition, update-preservation,
  and workflow-documentation cases are owned by issues #68–#73.
