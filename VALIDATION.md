# Validation record

Last executed: 2026-07-14 on macOS arm64 with CPython 3.14.6,
uv 0.11.28, just 1.56.0, and bun 1.3.9.

## Change validated

Completed benchmark runs now append one publication-oriented JSONL registry
row per arm, preserving the manifest's resolved Copier identity and the full
primary judge endpoint alongside quality, analyzer, coverage, cost, token,
tool-call, turn, and revision metrics. `just bench-report` renders the registry
as a standalone offline HTML comparison with grouped tables, identity filters,
quality/time/cost charts, separate token classes, and action-effort charts.
Missing or empty registries exit cleanly with a next-step message.

Template releases now use changelog-backed PEP 440 git tags. The first release,
`v0.1.0`, is an annotated tag on the committed Copier baseline. Generated
repositories document update checks and inline-conflict handling, and the
template configuration wires an empty migration list. A local, real-git test
generates from `v0.1.0`, observes `copier check-update --quiet` exit 2, updates
to the current ref with unchanged answers, observes exit 0, and proves the
updated repository's full gate offline.

## Commands and results

- `just release v0.1.0`: passed; created the annotated template release tag.
- `just validate`: passed.
  - Root suite: 154 passed in 45.09s. The single `DirtyLocalWarning` is expected
    from the test that deliberately creates a dirty temporary template repo.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated dependency resolution: 32 packages resolved; 31 installed.
  - Generated quality gate: all steps passed.
  - Offline update round trip: 1 passed in 15.59s after the current generated
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
