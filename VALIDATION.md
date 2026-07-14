# Validation record

Last executed: 2026-07-14 on macOS arm64 with CPython 3.14.6,
uv 0.11.28, just 1.56.0, and bun 1.3.9.

## Change validated

The generation engine was migrated from manual file copying, package-directory
renaming, and placeholder replacement to pinned Copier 9.17.0 behind the
unchanged `generate(...)` and `python-repo init` interfaces. The template now
uses `.jinja` files and a templated package path, records Copier provenance and
answers, takes artifact exclusions from `copier.yml`, and renders the current
worktree explicitly with `vcs_ref="HEAD"`. Wheel installs fall back to the
distribution release (`v0.1.0` in this run) when git metadata is unavailable.

## Commands and results

- `just validate`: passed.
  - Root suite: 126 passed. The eight `DirtyLocalWarning` messages are expected
    because validation deliberately includes the staged, uncommitted template.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated dependency resolution: passed.
  - Generated quality gate: all steps passed.
- `uv build --out-dir .packaging-check`: source distribution and wheel built.
- Wheel-installed `python-repo init wheel-check . --no-git`: passed; generated
  `.copier-answers.yml` recorded `_commit: v0.1.0`, `_src_path`, `project_name`,
  and `package`. The temporary packaging directory was removed afterward.

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
- Worktree generation requires git so Copier can record and render `HEAD`;
  installed wheels do not require git metadata and record the package version
  as their template release instead.
