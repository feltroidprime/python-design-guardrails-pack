# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #64 adds the reusable recursive N0 → N1 → N2 acceptance harness.

- One real-command test executes the specification's nineteen steps through
  `repoctl`, from a freshly rendered N0 through alpha and beta lifecycle changes.
- The test-only fixture injects alpha implementation and proof evidence through
  one documented seam; product evidence stays under `verification/modules/`.
- Alpha's product hashes are checked after beta creation and activation and
  after alpha retirement; the final runtime index contains beta only.
- Generated N1/N2 tests now derive their expected indexes from active
  declarations instead of assuming every repository remains N0.
- The full pre-push suite has an explicit ten-minute warm-cache budget because
  it includes the recursive acceptance walk; `just test-fast` remains the
  sub-minute feedback lane.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 just validate
```

The canonical command passed end to end:

- root Ruff repair/check was stable across 143 files, and the root suite passed
  **222 tests** with 15 dirty-template warnings in 186.26 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- generated tests passed **125 passed, 1 skipped, 3 deselected** with **95.65%
  coverage** (90% required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The recursive harness currently certifies one minimal proof-carrying alpha
  fixture. The remaining application-shape, mutation, scale, composition, and
  update-preservation cases are owned by issues #65–#73.
