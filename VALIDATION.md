# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #69 certifies a stateful workflow capability without adding a workflow
engine, persistence layer, scheduler, production template change, or harness
change.

- Detached repoctl plan/apply declares alpha's `clock` and `execution`
  outbound seams; the fixture never patches its declaration.
- One immutable `Run` value and four pure transition functions model ready,
  retryable, succeeded, and cancelled states.
- Application-owned clock and execution protocols are injected into three
  small application operations. Sentinel implementations prove both ports are
  called and their results influence observable run state.
- One Hypothesis `RuleBasedStateMachine` exercises failed-attempt → retry →
  success, cancellation, and restart sequences while asserting every terminal
  run is closed.
- A temporary direct wall-clock import/call in the generated alpha domain is
  rejected by the existing architecture guard and restored immediately.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q -x tests/recursive/test_shape_stateful_workflow.py
PYTHONDONTWRITEBYTECODE=1 just check
PYTHONDONTWRITEBYTECODE=1 just validate
```

The TDD red run failed at the intended missing fixture asset after 60.76
seconds. Subsequent focused runs exposed and corrected an oracle importing the
production entity (63.49 seconds), bare verification assertions plus a
positional boolean fact (63.13 seconds), and strict type warnings from untyped
state-machine lambdas and attributes (66.18 seconds).

The thermo-nuclear review then removed an unread attempt counter and redundant
per-rule property checks. The final focused #69 test passed **1 test** with one
dirty-template warning in 185.43 seconds. Root Ruff reported **152 files
already formatted** and no lint violations.

The canonical command passed end to end:

- root Ruff repair/check was stable across 152 files, and the root suite passed
  **227 tests** with 20 dirty-template warnings in 550.95 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- both generated gates passed **127 tests, 1 skipped, 3 deselected**, first in
  45.62 seconds and then in 41.30 seconds, with **95.65% coverage** (90%
  required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The successful root suite took 550.95 seconds, within the documented
  ten-minute warm-cache budget but with limited headroom for later recursive
  shape fixtures.
- The state machine uses deterministic in-memory sentinels. It certifies the
  state and port boundaries, not persistence, concurrency, scheduling, or a
  real execution backend.
- The remaining mutation, update-preservation, composition, and
  workflow-documentation cases are owned by issues #70–#73.
