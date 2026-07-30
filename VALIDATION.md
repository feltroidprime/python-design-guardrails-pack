# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #51 of epic #44 adds the repository-control capability plan/apply
boundary.

- `python -m repoctl capability plan NAME --output .repo/plans/NAME.json`
  writes one inspectable canonical plan through the repository port. Saved
  plan-control artifacts stay readable but are excluded from planning
  snapshots, so they do not make their own plan stale.
- `capability apply PLAN` validates the saved immutable plan, delegates to the
  #50 application protocol, and reports either `applied` or the idempotent
  `already_applied` result without re-writing the repository.
- The generated DRAFT capsule is structurally valid, contains only the seeded
  capability structure, and does not introduce a placeholder entity,
  `NotImplementedError`, or `assert True` test.
- Template sources were aligned with the rendered Ruff result because Jinja
  package imports are not parseable at the pack root; the downstream repair
  probe now remains stable after bootstrap.

## Commands and actual results

```bash
just validate
```

The final canonical `just validate` passed end to end (directly observed exit
code 0):

- root Ruff repair/check was stable across 135 files; root tests: **215
  passed** in 34.82s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- each generated full quality run reported **241 passed, 8 skipped, 3
  deselected** with **93.94%** coverage;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 59.95s**.

Additional downstream boundary check against a freshly rendered repository:

```bash
uv run python -m repoctl capability plan alpha --inbound python --output .repo/plans/alpha.json
uv run python -m repoctl capability apply .repo/plans/alpha.json
uv run python -m repoctl capability apply .repo/plans/alpha.json
uv run python -m scripts.capability_validator --root src/orchard_billing/modules/alpha
```

All commands exited 0. The first command emitted a 13-operation plan; the two
apply calls respectively returned `applied` and `already_applied`, and the
capability validator passed.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their symlink permissions and directory fsync behavior differ.
- The control CLI intentionally permits saved plans only under its reserved
  plan-control directory; use the application protocol's recovery instruction
  when a plan is stale or an interrupted journal requires recovery.
