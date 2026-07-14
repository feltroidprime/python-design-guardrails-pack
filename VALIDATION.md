# Validation record

Last executed: 2026-07-14 on macOS arm64 with CPython 3.14.6,
uv 0.11.28, just 1.56.0, and bun 1.3.9.

## Change validated

The benchmark now measures maintenance behavior after the initial build. A
fresh agent receives each arm's completed workspace and the same app-specific
change request; phase-specific probes, pinned analyzers, effort accounting, and
blind judging remain separated from the build phase in results, registry rows,
reports, and the TUI. Ledger and Relay ship precise maintenance requests and
regression probes, and the Relay reference implementation proves its complete
maintenance scenario is satisfiable.

Review follow-up extended the Ledger battery to cover invalid and custom
recurrence intervals. Relay now probes that JSON imports cannot mix legacy and
extended job schemas, that rejection appends nothing, and its reference
implementation enforces the same contract.

Matrix benchmark campaigns now expand builders, apps, seeds, named Copier
answer-set variants, and repetitions into deterministic cells. Campaigns pin
all cells to one immutable template snapshot, including dirty `HEAD`
experiments, and preserve the resolved revision and source digest in manifests
and registry rows. Snapshot commits and Copier answer provenance are stable
across resumed invocations. Validation rejects duplicate dimensions, OpenCode
roles without an explicit canonical family, builder/judge family overlap, and
unknown variants before execution. Matrix builders use the declared provider's
native model and effort defaults when omitted, while scheduling enforces
declared per-provider concurrency caps. Resume now hashes the complete
outcome-affecting build and maintenance configuration and skips only cells with
every expected arm/phase row. Matrix-selected named variants replace, rather
than combine with, the app's named variant; template symlinks are rejected
before any provider workspace can be created. Template file modes and the
configured provider-runner checkout are also part of the immutable cell
identity.

## Commands and results

- Focused maintenance regression command: 3 passed in 2.40s after first
  demonstrating that the mixed-schema Relay import was incorrectly accepted.
- Focused benchmark configuration, matrix, and pipeline suites: 109 passed in
  25.97s; the 18 `DirtyLocalWarning` instances reflected the intentionally
  uncommitted template-sensitive review fixes at that point.
- `just test`: passed; 211 passed in 63.94s. Its 24 `DirtyLocalWarning`
  instances likewise reflected the then-uncommitted review fixes.
- `just validate`: passed.
  - Root suite: 211 passed in 65.36s. The single `DirtyLocalWarning` is expected
    from the test that deliberately creates a dirty temporary template repo.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated dependency resolution: 32 packages resolved; 31 installed.
  - Generated quality gate: all steps passed.
  - Offline update round trip: 1 passed in 14.15s after the current generated
    gate warmed the pinned tool caches.

## Generated repository gate

- Ruff format and lint: passed.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- Architecture and documentation guards: passed.
- Import Linter: 2 contracts kept, 0 broken (22 files, 22 dependencies).
- Derived diagram sync and LikeC4 validation: passed.
- Tests: 23 passed.
- Branch-aware coverage: 93.30%, above the 90% floor.

## Remaining portability notes

- The first full validation on a machine may need network access to warm the
  pinned Python and LikeC4 caches. The update round-trip gate then runs with uv
  offline and package-manager network proxies pointed at an unreachable local
  endpoint.
- Real benchmark runs still require a compatible `headless_llm` checkout and
  authenticated provider CLIs; the deterministic fake-agent and reference
  implementation tests do not exercise a live provider.
- Local generation and downstream updates require git metadata. Installed
  wheels continue to fall back to their distribution version for Copier's
  recorded template identity.
