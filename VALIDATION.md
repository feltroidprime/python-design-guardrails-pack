# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #65 proves that independent capability order commutes and records the
100-capability command budgets.

- Generated proof evidence applies two distinct intents in both orders through
  the real planner and repository port, then compares canonical state digests
  that exclude plan and journal artifacts.
- The proof catalog exposes
  `REPOCTL::INDEPENDENT-CAPABILITIES-COMMUTE`; its focused proof and falsifier
  pass through `just prove-one`.
- A socket-blocked in-process probe builds 100 DRAFT capabilities and measures
  warm median `status`, capability-plan, capability-apply, and generation
  latency without including interpreter or dependency-startup time.
- The committed Linux x86_64/Python 3.14.6 record is within every explicit
  budget: 0.040029s status, 0.056325s plan, 0.236318s apply, and 0.042006s
  generation. Live misses are recorded and warned, not converted into flaky
  timing failures.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 just validate
```

The canonical command passed end to end:

- root Ruff repair/check was stable across 147 files, and the root suite passed
  **223 tests** with 16 dirty-template warnings in 231.23 seconds;
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
- The committed medians describe this machine and Python build rather than a
  portable performance guarantee. Budget misses on other hosts remain visible
  as recorded regressions without failing correctness checks.
- The remaining application-shape, mutation, composition, and
  update-preservation cases are owned by issues #66–#73.
