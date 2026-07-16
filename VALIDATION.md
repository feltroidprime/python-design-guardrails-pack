# Validation record — 2026-07-16

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just
1.56.0, Bun 1.3.9, Git 2.55.0, GitHub CLI 2.96.0, Copier 9.17.0, and
pytest-xdist 3.8.0. Copier emitted 21 expected `DirtyLocalWarning` instances
because the canonical template changes were intentionally uncommitted during
the pack tests.

## Change validated

The combined template includes two additive agent-facing capabilities:

- a closed, versioned CLI catalog with ordinary typed arguments, explicit stdin
  policy, structured outcomes, bounded composable queries, safe idempotent
  mutation replay, progressive help, and closed safety declarations;
- opt-in Claude Code and Codex session evidence through private package
  `session-profiler-optimizer` at immutable commit
  `6ace879e8642777658576a47e0f53b32a1ddc0f7`, injected only into
  `just session-log` and `just session-e2e`.

The item mutation and its idempotency replay record are atomic in both shipped
repository adapters. Same-key/same-normalized-input retries return the original
item without another item or event; conflicting reuse is stable and redacted.
Event publication remains post-commit and non-durable. Durable delivery would
require an application-owned transactional outbox and delivery contract.

Every declared command outcome now has an independent detached-process case.
Dependency failures use a real incompatible SQLite schema; unexpected failures
use a real broken stdout boundary. Help expectations independently pin every
argument's type, required/default state, choices, repeatability, and query
maximum where applicable. Decodable continuations with blank or newline
positions are rejected as `invalid_continuation` rather than translated as an
unexpected failure.

## Commands and actual results

### Canonical pack validation

```bash
just validate
```

Final result: passed.

- Pack tests: 237 passed with 21 expected warnings in 38.73s.
- Template cleanliness and complete Jinja rendering: passed.
- Fresh baseline `uv sync --all-groups`: resolved 23 packages without fetching
  the private profiler.
- Generated quality gate: Ruff format/lint, BasedPyright (0 errors, 0 warnings,
  0 notes), architecture, documentation, both import contracts, diagram sync,
  and LikeC4 validation all passed.
- Generated tests: 145 passed, 7 declared dormant variants skipped, 3 opt-in
  session tests deselected in 9.09s, with 93.44% branch coverage and no test
  warnings.
- Deterministic downstream repair probe: passed with no canonical drift.
- Previous-release and generated-recipe Copier update acceptance: 2 passed in
  22.19s.

The first post-rebase `just validate` reached the generated type gate and
failed exactly with:

```text
2 errors, 5 warnings, 0 notes
FAILED: types (exit 1)
VALIDATION FAILED at step: downstream check loop
```

The findings were five implicit string concatenations and an `Any`-typed
`CompletedProcess.args` in the new tests. Both were corrected before the final
passing run. A later passing run exposed two `ResourceWarning` messages from a
test SQLite connection; the connection was explicitly closed and the canonical
command above was rerun to the warning-free downstream result recorded here.

### Focused process-contract checks

From fresh generated repositories:

```bash
uv run pytest -q --no-cov tests/integration/test_cli_outcomes.py
uv run pytest -q --no-cov tests/integration/test_cli_input_contract.py
```

- The outcome suite first exposed three buffered broken-stdout cases, then
  passed all 14 cases in 2.06s after the child process became unbuffered.
- The input/help suite passed 9 cases in 1.03s with 3 stdin-accepting variants
  intentionally dormant.
- The focused blank-position continuation regression passed 1 case with 13
  outcome cases deselected.

### Opt-in private session consumer

From a separate fresh generated `orchard-billing` repository:

```bash
uv sync --all-groups
just session-e2e
```

Baseline sync resolved 23 packages without the private dependency. The opt-in
recipe then installed its isolated dependency set and converted five Claude and
five Codex primary sessions plus the deterministic generated fixture: 3 passed
in 1.13s.

## Tests added or updated

- Exact catalog-to-case completeness covers input, filters, selectable fields,
  safety, shared and command-owned outcomes, quiet output, and continuations.
- All outcome cases cross a detached process boundary; no runtime mock or
  in-process application seam remains in that suite.
- Shared memory/SQLite repository contracts cover concurrent atomic replay,
  conflicts, rollback, filtering, ordering, and projection.
- Consumer session tests pin ATIF-v1.7, raw-byte preservation, deterministic
  replay, the complete artifact set, and the exact manifest check vocabulary.
- Real-session E2E samples exactly five byte-size quantiles per available agent;
  zero sessions skips and one to four sessions fails clearly.
- Generator inventory and deterministic generated-tree digest include both
  feature sets and ADR-0004/ADR-0005 without numbering collisions.

## Remaining risks and portability notes

- Opt-in session commands require network access and authenticated read access
  to the private package, for example through `gh auth setup-git`; baseline
  bootstrap and CI do not.
- Harbor's native transcript conversion internals remain private. Pin updates
  must rerun that package's owned fixtures and real-session quintiles.
- Native logs may contain source, prompts, tool output, or echoed credentials.
  Output is Git-ignored and owner-only on POSIX; Windows relies on the
  containing directory's access controls.
- SQLite is the shipped cross-process atomic idempotency implementation. New
  persistence adapters must pass the shared contract and establish their own
  concurrency guarantees.
- Post-commit events can still be lost after database commit; products needing
  recovery must add a transactional outbox.
- First dependency resolution and LikeC4 validation require network access.
