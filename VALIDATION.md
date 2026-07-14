# Validation record

Last executed: 2026-07-14 on macOS arm64 with CPython 3.14.6,
uv 0.11.28, just 1.56.0, and bun 1.3.9.

## Change validated

Copier now exposes `precommit` and `agents_contract` feature-toggle questions
whose defaults reproduce the previous generated repository byte-for-byte.
The benchmark declares `no-precommit`, `no-agents-md`, and
`checks-via-commit` as named TOML answer sets. Deterministic generation tests
fix each variant's exact absent and modified paths, including the complete
hooks-first `AGENTS.md` content delta and removal of stale `AGENTS.md`
references from the no-contract README.

The fake-agent pipeline proves every variant configuration leaves the bare
workspace's Git tree unchanged. A completed hooks-first run records the same
variant and effective Copier answers in its workspace, manifest, results, and
both append-only registry rows. Config loading rejects unknown variants with
the complete known-name list and rejects attempts to override a named
variant's defining answer.

## Commands and results

- `just validate`: passed.
  - Root suite: 180 passed in 77.76s. The 22 `DirtyLocalWarning` instances are
    expected because generation tests intentionally exercise the dirty current
    worktree.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated dependency resolution: 32 packages resolved; 31 installed.
  - Generated quality gate: all steps passed.
  - Offline update round trip: 1 passed in 19.75s after the current generated
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
- Working-tree benchmark identity requires git. Release benchmarking should
  use a PEP 440 template tag in `[template] vcs_ref` for a stable identity.
- Real benchmark runs still require a compatible `headless_llm` checkout and
  authenticated provider CLIs; the deterministic fake-agent tests do not.
- Local generation and downstream updates require git metadata. Installed
  wheels continue to fall back to their distribution version for Copier's
  recorded template identity.
