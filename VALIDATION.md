# Validation record — 2026-07-16

Validated on macOS from the current dirty working tree, which also contained
the in-progress agent-native CLI changes described below. The environment used
Python 3.14.6, uv 0.11.28, just 1.56.0, bun 1.3.9, and git 2.55.0. Copier's 20
`DirtyLocalWarning` instances therefore accurately reported that the generated
snapshots included uncommitted template content. The generated repository
resolved prek 0.4.9 through its development group.

## Change validated

Generated repositories now expose one agent repair-and-verification route:
`just check`. Its repair phase applies safe Ruff fixes, Ruff formatting, and
derived-diagram regeneration before the same script runs the complete strict
gate. Pre-push and CI omit `--fix`, so publication still validates committed
content without mutating it. The downstream justfile no longer offers the
competing `fix`, `test`, or `arch` verification branches.

The generated `AGENTS.md` routes every coherent edit into one red/green check
loop with an explicit zero-exit completion criterion. Bootstrap, CLI next
steps, scaffold-update guidance, diagram documentation, and the pull-request
template all point to the same command.

Generated repositories now expose an agent-native CLI whose construction
prevents command drift. A closed command catalog owns command names, kinds,
arguments, output modes, paging limits, continuation policy, and retry
metadata. Parser construction, runtime dispatch, focused help, and the
versioned capabilities document derive from that catalog, while an independent
closed contract-case set must cover the same command set at the detached
process seam.

The sample application now uses bounded list queries and repository reads with
stable ordering and continuation tokens. Machine output uses versioned JSON
success and error envelopes with stable exit classes; human output remains
separate. Non-idempotent mutation behavior, invalid-input non-mutation,
dependency failures, unexpected-failure redaction, and opt-in debug details are
covered at both process and in-process seams.

New AST rules reject prompts, uncontrolled process exits, CLI-framework
leakage, and production command registration outside the catalog. ADR-0003,
the exception ledger, downstream agent guidance, generated architecture model,
and the pack's design-to-guardrail documentation describe the contract and its
versioning policy.

## Commands and results

- Targeted red/green contract slices were run throughout implementation for
  capabilities, bounded pagination, mutation replay, invalid-input safety,
  help discovery, catalog completeness, process error redaction, and the four
  new CLI architecture rules. Each slice failed for the intended missing
  behavior before its implementation and passed afterward.
- `uv run ruff format --check .` and `uv run ruff check .` in an intermediate
  generated repository — passed: 48 files formatted and all lint checks clean.
- `uv run basedpyright --project pyproject.toml` in the generated repository —
  passed: 0 errors, 0 warnings, 0 notes. The downstream gate now supplies the
  project explicitly so an unrelated parent configuration cannot capture it.
- `just validate` — passed.
  - Pack tests: 226 passed in 76.22s; 20 expected `DirtyLocalWarning`
    instances reported the uncommitted template diff.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - The generated check loop restored deliberately seeded Python formatting
    and diagram drift, changed no other generated source, then passed the full
    quality gate.
  - Copier update round trip with the downstream gate enabled: 1 passed in
    15.62s.

## Tests added or updated

- Added a generated-justfile contract that fixes the recipe surface at
  `default`, `bootstrap`, `check`, `diagrams`, and `update`, with `just check`
  as the only repair-and-verification route.
- Extended pack validation with deliberate Ruff/format and diagram drift
  probes. Validation requires `just check` to restore both probes while leaving
  every other generated source file byte-identical.
- Updated the hooks-first materialization test to require the same local check
  loop plus successful commit and pre-push publication hooks.
- Added an independent, typed CLI contract-case catalog and exhaustive
  completeness checks against the production catalog.
- Added detached-process tests for every current command's success and failure
  contracts, bounded paging, mutation replay/readback, human output, focused
  help, JSON schemas, and hidden versus debug unexpected failures.
- Added closed contract variants for query, mutation, streaming,
  interactive-bootstrap, and bulk-export commands. The last three tests skip
  until a command of that kind is registered, then become mandatory through
  catalog completeness.
- Added protocol serialization unit tests for every closed command kind and
  root tests for CLI AST guard violations and documented suppressions.
- Updated repository contracts, application tests, wiring tests, generated-file
  inventory, and the deterministic generated-tree digest for bounded queries
  and the new CLI modules.

## Generated repository gate

- Ruff format: 48 files already formatted; lint passed.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- Architecture and documentation guards: passed.
- Import Linter: 2 contracts kept, 0 broken across 26 files and 35
  dependencies.
- Derived diagram sync and pinned LikeC4 validation: passed.
- Tests: 58 passed and 3 intentionally dormant command-kind cases skipped in
  3.95s.
- Branch-aware coverage: 91.19%, above the 90% floor.

## Remaining portability notes

- The first full validation on a machine may need network access to resolve the
  pinned Python and LikeC4 toolchains.
- Process-contract tests require a platform that supports subprocess timeouts
  and detached standard input; they do not require a TTY.
- Unexpected-failure debug details are intentionally diagnostic and are not a
  stable machine protocol. The default JSON error envelope is the supported
  automation contract.
