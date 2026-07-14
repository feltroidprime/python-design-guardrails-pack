# Validation record

Last executed: 2026-07-14 on macOS arm64 with CPython 3.14.6,
uv 0.11.28, just 1.56.0, and bun 1.3.9.

## Change validated

The benchmark harness now selects the template arm through pinned Copier with
an explicit `[template]` configuration. Manifests, `results.json`, and reports
record the resolved template version, variant, and effective answers. `HEAD`
records a dirty-flagged git-describe identity for working-tree experiments;
release tags stay pinned to their committed content. Non-baseline variants
fail fast until feature-toggle questions ship, Copier prompting is disabled,
and `.copier-answers.yml` is excluded symmetrically from judge bundles.

## Commands and results

- `just validate`: passed.
  - Root suite: 150 passed in 38.32s. The single `DirtyLocalWarning` is expected
    from the test that deliberately creates a dirty temporary template repo.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated dependency resolution: passed.
  - Generated quality gate: all steps passed.
- `just test`: 150 passed in 40.16s with the same one expected warning.

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
