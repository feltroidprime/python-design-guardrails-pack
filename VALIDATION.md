# Validation record

Last executed: 2026-07-11, macOS (arm64), CPython 3.14.6, uv 0.11.28, via `just validate`.

This record supersedes the original release validation, which ran on a Python
3.13 sandbox simulating lazy annotations. That simulated run over-reported
coverage (90.76%); on real Python 3.14 the original template measured 88.75%
and failed its own 90% floor. Two missing domain tests (`Item.rename` and the
over-length `ItemName` rejection) were added to `template/` to close the gap.

## Pack-level checks (`just validate`)

- Generator test suite (`tests/test_instantiate.py`): 19 passed — name
  validation, non-empty-directory refusal, package renaming, full placeholder
  replacement, cache-artifact exclusion, expected-file preservation, and
  executable behavior of the generated architecture guard and example slice.
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
- Tests: 9 passed with sockets disabled.
- Branch-aware coverage: 92.50%, above the 90% floor.

## Known limitations

- `application/ports.py` measures 0% covered: it is a type-only module (all
  imports of it are under `TYPE_CHECKING`), so it is never imported at
  runtime. The overall floor still holds; do not "fix" this by weakening the
  coverage configuration.
- Validation runs the toolchain pinned by the template (uv-managed Python
  3.14); the first run needs network access to resolve dependencies.
