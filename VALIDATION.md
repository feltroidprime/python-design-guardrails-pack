# Validation record

Last executed: 2026-07-11, macOS (arm64), CPython 3.14.6, uv 0.11.28,
bun 1.3.9, via `just validate` — after adding the derived LikeC4
architecture diagrams (sync script, gate checks, and template files).

## Pack-level checks (`just validate`)

- Generator test suite (`tests/test_instantiate.py`): 22 passed — name
  validation, non-empty-directory refusal, package renaming, full placeholder
  replacement, cache-artifact exclusion, expected-file preservation,
  executable behavior of the generated architecture guard and example slice,
  and the diagram sync script (fresh `--check` passes, planted-module drift
  fails and names the fix command, `--write` resolves it, output byte-stable
  across runs). Diagram sync tests run with grimp only — no Bun.
- Template cleanliness: no local runtime artifacts under `template/`.
- Fresh instantiation (`orchard-billing` / `orchard_billing`) in a temporary
  directory: no placeholder token survived in any file name or file content.

## Generated repository checks (its own `scripts/quality_gate.py`)

- `uv lock --check`: passed.
- Ruff formatting and linting: passed.
- BasedPyright, `pythonVersion = "3.14"`, recommended mode,
  `failOnWarnings = true`, explicit `Any` errors: 0 errors, 0 warnings.
- Repository AST architecture guard: passed.
- Import Linter: 2 contracts kept, 0 broken.
- Diagram sync: derived LikeC4 model matches the import graph.
- Diagram views: `bunx likec4@1.58.0 validate` — 4 source files, valid.
- Tests: 9 passed with sockets disabled.
- Branch-aware coverage: 92.50%, above the 90% floor.

## Known limitations

- `application/ports.py` measures 0% covered: it is a type-only module (all
  imports of it are under `TYPE_CHECKING`), so it is never imported at
  runtime. The overall floor still holds; do not "fix" this by weakening the
  coverage configuration.
- Validation runs the toolchain pinned by the template (uv-managed Python
  3.14); the first run needs network access to resolve dependencies and, once
  per machine, for `bunx` to download the pinned LikeC4 CLI.
