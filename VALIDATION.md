# Validation record — 2026-07-29

Validated on macOS 26.5 (Darwin 25.5.0, arm64) with Python 3.14.6, uv 0.11.32,
just 1.57.0, Copier 9.17.0, pytest 9.1.1, and pytest-xdist 3.8.0.

## Change validated

Two removals, both narrowing the configuration surface:

- **The `precommit` Copier question is gone; hooks are unconditional.** The
  hook policy file moved from
  `template/{% if precommit and not workspace_member %}prek.toml{% endif %}` to
  `template/{% if not workspace_member %}prek.toml{% endif %}`, and the
  `{% if precommit %}` branches in `template/justfile.jinja`,
  `template/pyproject.toml.jinja`, and `template/README.md.jinja` were
  collapsed to their true arm. `just bootstrap` and `just update` always run
  `uv run prek install -f` / `uv run prek update` in standalone repositories,
  and the `prek>=0.4.9` dev dependency is always present. Workspace members are
  unchanged: the root still owns hooks, the lockfile, and the dev group.
- **The end-to-end value benchmark harness is gone.** `benchmarks/` (harness,
  configs, prompts, matrices, experiments, figures, report), its eight test
  modules, `tests/fixtures/`, and the `just benchmark`, `just
  benchmark-matrix`, `just benchmark-matrix-plan`, `just bench-report`, and
  `just bench-figures` recipes were deleted. The harness was maintainer-only
  tooling; nothing under `template/` referenced it, so generated repositories
  are byte-identical with respect to this removal.

Documentation was updated in the same change: the root `README.md` lost the
"Measure it" section and the benchmark design-choice row, `DESIGN_GUARDRAILS.md`
no longer describes a `precommit = true` materialization or benchmark
ablations, `.github/workflows/quality.yml` no longer cites the benchmark
campaign tests as a reason for full history, and `CHANGELOG.md` records both
removals under `[Unreleased]`.

`tests/test_instantiate.py` lost
`test_delta_or_identical_no_precommit_has_exact_file_delta` (its variant no
longer exists) and the two remaining `precommit` answers were dropped from
`test_generated_gate_rejects_tracked_unimported_python_syntax` and
`test_delta_or_identical_explicit_default_toggles_are_byte_identical_to_defaults`.
Strict undefined in Copier means any surviving `precommit` reference under
`template/` would fail generation outright; `just validate` proves none remain.

## Commands and actual results

```bash
just test      # 199 passed, 10 warnings in 61.43s
just validate
```

`just validate` passed end to end: the generator suite, template-cleanliness
and full-rendering checks, dependency resolution, bootstrap-drift repair, the
generated repository's own quality gate, both shared prek shims executed from a
linked worktree (all hooks `Passed`), and the update round-trip phase
(**2 passed in 41.04s**). The intermediate `fail verdict` line is the
deliberate doctor fault-injection probe, not a regression.

## Remaining risks and portability notes

- Removing a Copier question is a breaking answer-schema change for downstream
  repositories generated with `precommit = false`. On the next
  `just scaffold-update`, Copier drops the stale answer and materializes
  `prek.toml`, the `prek` dev dependency, and the hook install/update steps.
  That is the intent, but such repositories will see a non-trivial three-way
  merge and must run `just bootstrap` afterwards to install the shims.
- No migration entry was added to `copier.yml` `_migrations`; the answer is
  simply ignored. Add one only if a downstream repository needs the removal
  handled programmatically.
- Deleting `benchmarks/` removes the only reproducible evidence pipeline for
  the pack's value claims. If that evidence is wanted again, it must be
  rebuilt from Git history (the tree is preserved in commits before this
  change).
- The root project deliberately has no development virtual environment, so
  focused pytest commands must go through `uv run --no-project`.
