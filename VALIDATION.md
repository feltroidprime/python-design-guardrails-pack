# Validation record — 2026-07-16

Validated on macOS with Python 3.14.6, uv 0.11.28, just 1.56.0, Bun
1.3.9, Git 2.55.0, and Copier 9.17.0. The pack branch's tracked tree was
clean during final validation. An unrelated pre-existing untracked research
document remained outside `template/`; Copier therefore emitted 21 honest
`DirtyLocalWarning` instances, but the document was not part of any generated
repository.

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

## Pack commands and results

- Targeted TDD slices failed first for the missing durable `_src_path`, missing
  recipe, missing non-interactive defaults, and inherited bytecode-prefix
  behavior; each passed after its corresponding implementation.
- `just test` before the integration proof — passed: 226 tests. The final
  commit hook passed with the new regression included: 227 tests.
- Final `just validate` — passed.
  - Pack tests: 227 passed in 83.17s; 21 expected `DirtyLocalWarning`
    instances.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: fully rendered, dependencies resolved,
    and `just check` passed.
  - Generated gate: Ruff format/lint passed; BasedPyright reported 0 errors,
    0 warnings, and 0 notes; both architecture contracts were kept; docs,
    diagrams, and LikeC4 validation passed.
  - Generated tests: 58 passed, 3 intentionally dormant command-kind cases
    skipped, and branch coverage was 91.19% against the 90% floor.
  - Copier previous-release update round trip with the downstream gate enabled:
    1 passed in 17.33s.

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
