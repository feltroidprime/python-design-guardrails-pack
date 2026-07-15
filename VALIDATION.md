# Validation record — 2026-07-16

Validated on macOS in a clean detached worktree of the exact implementation
commit, with Python 3.14.6, uv 0.11.28, just 1.56.0, bun 1.3.9, and git 2.55.0.
The generated repository resolved prek 0.4.9 through its pinned development
group; a system-wide `prek` command was not installed in the validation
environment.

## Change validated

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
  help discovery, catalog completeness, process error redaction, effectful
  streaming controls, readback after every invalid case, indirect parser
  registration, unpacked parser keywords, and the four new CLI architecture
  rules. Each slice failed for the intended missing behavior before its
  implementation and passed afterward.
- `uv run ruff format --check .` and `uv run ruff check .` in an intermediate
  generated repository — passed: 48 files formatted and all lint checks clean.
- `uv run basedpyright --project pyproject.toml` in the generated repository —
  passed: 0 errors, 0 warnings, 0 notes. The downstream gate now supplies the
  project explicitly so an unrelated parent configuration cannot capture it.
- `just validate` — passed.
  - Pack tests: 225 passed in 71.79s; one expected `DirtyLocalWarning` came
    from the test that deliberately exercises dirty-template identity.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated repository full quality gate: passed.
  - Copier update round trip with the downstream gate enabled: 1 passed in
    17.79s.

## Tests added or updated

- Added an independent, typed CLI contract-case catalog and exhaustive
  completeness checks against the production catalog.
- Added detached-process tests for every current command's success and failure
  contracts, bounded paging, mutation replay/readback, no-effect readback after
  invalid cases, human output, focused help, JSON schemas, and hidden versus
  debug unexpected failures.
- Added closed contract variants for query, mutation, streaming,
  interactive-bootstrap, and bulk-export commands. The last three tests skip
  until a command of that kind is registered, then become mandatory through
  catalog completeness. Streaming cases require a contrasting unfiltered,
  over-limit baseline; bulk invalid cases require an absent destination probe.
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
  3.61s.
- Branch-aware coverage: 91.19%, above the 90% floor.

## Remaining portability notes

- The first full validation on a machine may need network access to resolve the
  pinned Python and LikeC4 toolchains.
- Process-contract tests require a platform that supports subprocess timeouts
  and detached standard input; they do not require a TTY.
- Unexpected-failure debug details are intentionally diagnostic and are not a
  stable machine protocol. The default JSON error envelope is the supported
  automation contract.
