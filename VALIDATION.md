# Validation record — 2026-07-15

Validated on macOS in the repository worktree with Python 3.14.6, uv,
just 1.56.0, bun 1.3.9, git 2.55.0, and prek 0.4.9.

## Change validated

The pack root and generated repositories now use j178/prek as their only Git
hook manager. Both native `prek.toml` configurations preserve the previous
commit and pre-push stages, while the generated project resolves prek from its
uv dev group and uses native `prek install`, `prek run`, and `prek update`
commands.

The legacy `.pre-commit-config.yaml` files and `pre-commit` dependency and
commands were removed. The Copier answer key remains `precommit` so existing
answer files and update workflows keep their public contract; it now controls
whether the prek policy is rendered.

Root and downstream documentation, benchmark fixture manifests, agent
contracts, CLI next steps, version-coherence instructions, and deterministic
generation expectations were synchronized.

## Commands and results

- `tmpdir="$(mktemp -d)"; cp 'template/{% if precommit %}prek.toml{% endif %}'
  "$tmpdir/prek.toml"; uvx --from prek==0.4.9 prek validate-config prek.toml
  "$tmpdir/prek.toml"` — passed: both native TOML configurations were valid.
- `uv run --no-project --python 3.14 --with pytest==9.1.1 --with
  copier==9.17.0 --with grimp==3.15 pytest -q tests/test_instantiate.py
  tests/test_benchmark_config.py` — passed: 83 tests in 30.69s; five expected
  `DirtyLocalWarning` instances reported the uncommitted template changes.
- `uvx --from prek==0.4.9 prek run pack-tests --all-files` — passed after
  synchronizing one stale benchmark wording assertion; prek executed the root
  `pack-tests` hook successfully.
- `just validate` — passed.
  - Pack tests: 206 passed in 64.21s; 20 expected `DirtyLocalWarning`
    instances reported the uncommitted template changes.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Dependency resolution installed `prek==0.4.9` with the generated dev group.
  - Generated repository full quality gate: passed.
  - Offline Copier update round trip: 1 passed in 15.55s.

## Tests added or updated

- Added a generated-repository invariant test for `prek.toml`, the minimum
  prek version, installed hook stages, dev dependency, and native justfile
  commands.
- Updated the expected generated tree and the exact `precommit=false` file
  delta from `.pre-commit-config.yaml` to `prek.toml`.
- Updated CLI next-step and hooks-first benchmark assertions to enforce prek
  wording and commands.
- Updated benchmark fixture manifests so the template arm copies `prek.toml`.

## Generated repository gate

- Ruff format: 40 files already formatted; lint passed.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- Architecture and documentation guards: passed.
- Import Linter: 2 contracts kept, 0 broken.
- Derived diagram sync and LikeC4 validation: passed.
- Tests: 23 passed in 2.53s.
- Branch-aware coverage: 93.30%, above the 90% floor.

## Remaining portability notes

- The first full validation on a machine may need network access to resolve
  Python hook environments and warm the pinned LikeC4 cache.
- Root contributors install prek once with `uv tool install prek`; generated
  repositories receive it through `uv sync --all-groups`.
- Existing clones that installed legacy pre-commit shims must run
  `prek install -f` once; the documented bootstrap command performs this
  replacement.
