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

## Commands and results

- `just validate`: passed.
  - Root suite: 155 passed in 40.53s. The single `DirtyLocalWarning` is expected
    from the test that deliberately creates a dirty temporary template repo.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated dependency resolution: passed.
  - Generated quality gate: all steps passed.
- `just test`: 155 passed in 43.63s with the same single expected
  `DirtyLocalWarning`.
- `tests/test_benchmark_report.py::test_just_bench_report_renders_fixture_registry`:
  1 passed in 0.26s, confirming the `just bench-report` integration directly.

## Generated repository gate

- Ruff format and lint: passed.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- Architecture and documentation guards: passed.
- Import Linter: 2 contracts kept, 0 broken (22 files, 22 dependencies).
- Derived diagram sync and LikeC4 validation: passed.
- Tests: 23 passed.
- Branch-aware coverage: 93.30%, above the 90% floor.

## Remaining portability notes

- The first validation on a machine may need network access for pinned Python
  dependencies and the pinned LikeC4 CLI.
- Working-tree benchmark identity requires git. Release benchmarking should
  use a PEP 440 template tag in `[template] vcs_ref` for a stable identity.
- Real benchmark runs still require a compatible `headless_llm` checkout and
  authenticated provider CLIs; the deterministic fake-agent tests do not.
- The HTML is dependency-free and its content, grouping, filters, asset URLs,
  and JavaScript syntax are deterministic-test covered. No browser backend was
  available in this session for an additional live visual smoke test.
