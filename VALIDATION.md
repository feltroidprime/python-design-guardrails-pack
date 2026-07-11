# Validation record

The template was instantiated as a throwaway project and checked with the pinned toolchain.

## Static and architecture checks

- Ruff formatting: passed.
- Ruff linting: passed.
- BasedPyright with `pythonVersion = "3.14"`, recommended mode, `failOnWarnings = true`, and explicit `Any` errors: 0 errors, 0 warnings.
- Repository AST architecture guard: passed.
- Import Linter: 2 contracts kept, 0 broken.
- Negative mutation: adding `import requests` inside `domain` produced `ARCH011` and a non-zero exit.

## Runtime tests

- 7 tests passed.
- Branch-aware coverage: 90.76%, above the configured 90% floor.
- Network sockets were disabled during tests.

The sandbox did not contain Python 3.14 and could not resolve the standalone Python download host. Runtime behavior was therefore exercised in a throwaway Python 3.13 copy with deferred annotations enabled solely to simulate Python 3.14's native lazy annotation behavior. The delivered template itself remains 3.14-only, contains no future-annotations import, and its generated GitHub Actions workflow requests Python 3.14.
