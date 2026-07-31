# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Git 2.54.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0,
Ruff 0.16.1, and prek 0.4.11.

## Change validated

Generated repositories now run Python-language prek hooks with Python 3.14,
matching their declared interpreter and the syntax emitted by the template.
This prevents `check-ast` and `debug-statements` from parsing Python 3.14 code
with an unrelated Python 3.13 hook environment during the initial commit.

- `prek.toml` sets `default_language_version.python = "python3.14"`.
- The initializer still renders current worktree changes from an editable pack
  installation, but suppresses Copier's expected `DirtyLocalWarning`; other
  Copier warnings remain visible.
- Generator tests assert the rendered hook interpreter and keep direct Copier
  test helpers free of the same expected dirty-template warning.
- The downstream README and guardrail map document the interpreter alignment.

## Commands and actual results

```bash
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q \
  tests/test_instantiate.py::test_generated_repository_uses_prek_for_git_hooks \
  tests/test_instantiate.py::test_generation_uses_current_dirty_worktree_instead_of_latest_tag

uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q -W error::copier.errors.DirtyLocalWarning \
  tests/test_instantiate.py

uv run --no-project --python 3.14 --with . \
  python-repo init hook-smoke /tmp/python-repo-macos.PA8pP7 --no-github

just validate
```

The two focused regressions passed **2 tests** in 2.33 seconds. The complete
generator module passed **56 tests** in 42.45 seconds while treating any
uncaught `DirtyLocalWarning` as an error.

The initializer smoke test generated and bootstrapped a fresh repository,
passed its quality gate (**127 passed, 1 skipped, 3 deselected; 95.65%
coverage**), and completed the initial commit after all prek hooks passed,
including `check-ast` and `debug-statements`. Because the smoke command ran the
CLI inside an ephemeral `uv run --with .` build environment, nested generated
`uv` commands printed `VIRTUAL_ENV` mismatch warnings; an installed
`python-repo` tool does not have that nested harness condition.

The final canonical `just validate` command passed end to end:

- root Ruff repair/check was stable across **154 files**, and the root suite
  passed **244 tests** in 619.18 seconds with no warning summary;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- the first two visible generated gate executions each passed **127 tests,
  1 skipped, 3 deselected**, in 33.62 and 31.43 seconds, with **95.65%
  coverage** (90% required);
- the initial commit passed every prek hook with the Python 3.14 hook policy;
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit and pre-push probes passed. The linked
  pre-push hook reported its full quality gate passed.

The generated contract placeholder skip, syntax failure, dirty-tree failure,
and offline doctor warnings printed during validation are deliberate probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64. The reported failure came from macOS
  arm64, but this environment could not execute the final acceptance run on
  macOS; prek's documented Python toolchain resolution and the generated
  configuration are platform-independent.
- The root suite took 619.18 seconds under concurrent host load, slightly over
  the ten-minute warm-cache budget. No test timed out or failed.
- Existing generated repositories retain their old `prek.toml`; regenerate or
  add `default_language_version.python = "python3.14"`, then reinstall hooks
  with `uv run prek install -f`.
