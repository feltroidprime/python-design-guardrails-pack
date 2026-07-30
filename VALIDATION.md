# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #53 of epic #44 adds detached-process contract evidence for every
`repoctl` control-plane command.

- `tests/repoctl/contract/cli_process_cases.py` defines nine public-boundary
  subprocess cases. Each invokes `python -m repoctl` with closed standard input
  and captures its two output streams without inspecting command implementation.
- The cases cover default JSON envelopes, status, capability planning, unknown
  commands, invalid plan schema, stale plans, plan-output conflicts, repeated
  application, and bounded capability continuation tokens.
- `tests/repoctl/contract/test_repoctl_cli_contract.py` verifies successful
  JSON envelope shape and empty stderr, error stream separation and error
  envelope shape (including retryability and corrective hints), traceback/ANSI
  stream sanitation, fixture-specific outcomes, closed stdin, and dynamic
  coverage of every public control-plane catalog command.

## Commands and actual results

```bash
uv run pytest -q -m contract tests/repoctl/contract/test_repoctl_cli_contract.py
just test
just validate
```

The focused, freshly rendered acceptance command reported **11 passed** in
2.02s. Root `just test` reported **215 passed** in 27.01s.

The final canonical `just validate` passed end to end (directly observed exit
code 0):

- root Ruff repair/check was stable across 139 files; root tests: **215
  passed** in 39.01s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- each generated full quality run reported **252 passed, 8 skipped, 3
  deselected** with **93.94%** coverage;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 64.40s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess environment and filesystem behavior can differ.
- The detached-process evidence intentionally inherits the generated Python
  executable and uses a generated-project `PYTHONPATH`, matching the supported
  module invocation rather than an installed console-script environment.
