# Validation record — 2026-07-16

Validated on macOS with Python 3.14.6, uv 0.11.28, just 1.56.0, Bun
1.3.9, Git 2.55.0, Copier 9.17.0, and pytest-xdist 3.8.0. The final run's
tracked changes were the root-only parallel-test command, its deterministic
concurrency regression, and their documentation; all template changes were
committed. An unrelated pre-existing untracked research document also remained
outside `template/`. Copier therefore emitted 21 honest `DirtyLocalWarning`
instances, but none of that root-only dirt was part of a generated repository.

## Change validated

Repositories created by the packaged `python-repo` CLI now record the durable
GitHub pack URL as Copier's `_src_path`, while direct development copies keep
their explicit Git source. The installed distribution version remains the
fallback `_commit`, so a released wheel and its matching template tag retain
coherent provenance.

Generated repositories now expose a real `just scaffold-update` recipe. It
runs the pinned Copier 9.17.0 through `uvx`, reuses recorded answers
non-interactively, performs Copier's three-way merge with inline conflicts,
and unsets the justfile's project-local `PYTHONPYCACHEPREFIX` for the tool run.
That last isolation prevents an update before bootstrap from creating an
invalid `.venv/pycache` directory that blocks subsequent `uv run` commands.
`just update` remains the separate dependency-and-hook update route.

The generated README documents the pinned availability check, the new recipe,
the clean-branch requirement, conflict resolution, and the downstream gate.
Root maintainer documentation records the durable provenance behavior and the
new Copier pin location.

The root generator suite now uses adaptive pytest-xdist workers with
module-scoped scheduling. The separate two-test update acceptance run uses two
workers. Both commands remain venv-less and pinned through `uv run
--no-project --with`.

## Pack commands and results

- Targeted TDD slices failed first for the missing durable `_src_path`, missing
  recipe, missing non-interactive defaults, and inherited bytecode-prefix
  behavior; each passed after its corresponding implementation.
- `just test` before the integration proof — passed: 226 tests. The final
  validation included the recipe and agent-contract regressions: 229 tests.
- Final `just validate` — passed.
  - Pack tests: 229 passed in 38.01s; 21 expected `DirtyLocalWarning`
    instances.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: fully rendered, dependencies resolved,
    and `just check` passed.
  - Generated gate: Ruff format/lint passed; BasedPyright reported 0 errors,
    0 warnings, and 0 notes; both architecture contracts were kept; docs,
    diagrams, and LikeC4 validation passed.
  - Generated tests: 58 passed, 3 intentionally dormant command-kind cases
    skipped, and branch coverage was 91.19% against the 90% floor.
  - Copier update acceptance: the previous-release round trip with its
    downstream gate plus a real generated-recipe transition both passed (2
    tests in 17.80s).
  - Total `just validate` wall time: 69.88s.

## Parallel-test benchmark

The same 229-test suite passed at every measured worker count:

- Serial baseline: 91.55s.
- 4 workers with `--dist loadscope`: 40.32s.
- 8 workers with `--dist loadscope`: 38.01s.
- Adaptive `-n auto --dist loadscope`: 39.80s during comparison and 38.01s
  in the final canonical validation.

The adaptive configuration was selected over a fixed eight workers because it
retains nearly all of the speedup while scaling to the CPU count of other
machines. The canonical test phase is 58.5% faster than the serial baseline.
The first parallel commit hook exposed a scheduler-timing assumption in the
matrix concurrency test; its fake runners now synchronize on the required
two-worker peak, and the full parallel suite passed twice afterward.

## Real repository proof: `blerdis`

Validation used the isolated branch `codex/validate-scaffold-update` in a
separate worktree, leaving the user's dirty `blerdis` main checkout untouched.
A temporary local annotated `v0.1.1` candidate tag exercised Copier's normal
newest-tag selection and was deleted afterward.

- Before update, `uvx --from copier==9.17.0 copier check-update --quiet`
  returned 2, meaning an update was available.
- The first recipe run correctly refused an uncommitted bootstrap recipe,
  proving the clean-branch precondition.
- The next run exposed Copier's non-TTY prompt failure; adding `--defaults`
  made the recipe non-interactive.
- The following downstream gate exposed `.venv/pycache` poisoning from the
  inherited `PYTHONPYCACHEPREFIX`; unsetting it around `uvx` fixed the recipe
  and gained an automated regression test.
- The corrected `just scaffold-update` advanced `.copier-answers.yml` to
  `v0.1.1` with no unmerged paths, inline markers, or whitespace errors.
- `just check` passed every downstream check: 58 tests passed, 3 skipped, and
  coverage was 91.19%.
- Re-running `just scaffold-update` reported `Keeping template version 0.1.1`;
  `check-update` returned 0 and the validation branch remained clean.

## Tests added or updated

- Generated provenance assertions now require the durable GitHub source for
  packaged generation and preserve the wheel-version fallback.
- The generated-justfile contract now requires `scaffold-update` and its exact
  pinned, non-interactive, environment-isolated Copier invocation.
- A public-recipe regression runs `just scaffold-update` against a PATH-stubbed
  `uvx` boundary and proves the project `.venv` is not created.
- Generated README assertions and the deterministic generated-tree digest were
  updated for the new workflow.
- The existing release-to-release acceptance test continues to prove Copier's
  clean three-way update and the updated repository's full downstream gate.
  A second two-tag acceptance test invokes the generated recipe against its
  recorded Git source and proves the next tagged template artifact arrives.

## Remaining portability and release notes

- Existing generated repositories do not already contain `scaffold-update`;
  they need the documented one-time Copier command or an equivalent temporary
  recipe to receive it. Subsequent updates use the recipe.
- Remote discovery requires a matching annotated pack tag and released wheel.
  The local `v0.1.1` validation tag was intentionally removed; publishing the
  next release remains a separate maintainer action.
- The first update on a machine may require network access for the pinned
  Copier tool and template Git source. The first full downstream gate may also
  resolve Python and LikeC4 toolchains.
