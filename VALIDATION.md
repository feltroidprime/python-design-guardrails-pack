# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #52 of epic #44 adds independent state-machine evidence for the
repository capability protocol.

- `verification/harness/repository_model.py` is a primitive-only reference
  model for capability lifecycle status, declarations, product-byte hashes,
  derived-index membership, and successful plan IDs. It imports no `repoctl`
  application or domain implementation.
- `verification/repoctl/test_repository_state_machine.py` drives the live
  memory repository through planning, first application, immediate replay,
  stale-plan rejection, a manual product edit, a second capability, and index
  regeneration. Its invariant rejects changed product bytes, duplicate
  successful plan IDs, and paths outside the allowed roots.
- The deliberate unsafe overwrite mutation produces a two-step counterexample
  against that model. The focused `-m stateful` command bypasses product
  coverage only for verification-only paths; the normal full quality gate
  retains its 90% floor.
- During validation, #51's Jinja package import was made safe for both short
  and long rendered package names: its long import is format-stable and its
  product/repoctl import groups are explicitly split so Ruff repairs do not
  create drift in either fresh renders or Copier updates.

## Commands and actual results

```bash
just validate
```

The final canonical `just validate` passed end to end (directly observed exit
code 0):

- root Ruff repair/check was stable across 137 files; root tests: **215
  passed** in 34.44s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- each generated full quality run reported **241 passed, 8 skipped, 3
  deselected** with **93.94%** coverage;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 62.16s**.

Additional focused checks against a freshly rendered repository:

```bash
HYPOTHESIS_PROFILE=fast uv run pytest -q -m stateful verification/repoctl/test_repository_state_machine.py
uv run pytest -q --no-cov verification/repoctl/test_repository_state_machine.py
just prove
```

All commands exited 0. The exact stateful acceptance command reported **1
passed, 2 deselected** in 0.22s; the complete state-machine module reported
**3 passed** in 1.03s; and the proof loop reported **38 passed, 26 deselected**.
The focused acceptance command emitted the expected coverage-library warnings
because it does not exercise the generated product package and disables coverage
reporting and enforcement for that narrowly selected run.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their symlink permissions and directory fsync behavior differ.
- The control CLI intentionally permits saved plans only under its reserved
  plan-control directory; use the application protocol's recovery instruction
  when a plan is stale or an interrupted journal requires recovery.
