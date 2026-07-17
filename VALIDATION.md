# Validation record — 2026-07-17

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just
1.56.0, Bun 1.3.9, Git 2.55.0, GitHub CLI 2.96.0, Copier 9.17.0, and
pytest-xdist 3.8.0. Copier emitted 22 expected `DirtyLocalWarning` instances
because the canonical changes were intentionally uncommitted during the pack
tests.

## Change validated

`python-repo init` now owns the complete standalone-repository setup:

1. render the template;
2. initialize Git on `main`;
3. run `just bootstrap`, which resolves dependencies, installs the prek
   commit and pre-push shims, and passes the generated quality gate;
4. commit the bootstrapped baseline;
5. optionally create and push the GitHub repository.

Bootstrap failure stops before the initial commit and GitHub creation. The
generation-only `--no-git` escape hatch intentionally skips bootstrap because
prek requires a Git repository.

Git stores hooks in its common directory, so the installed prek shims are
automatically shared by linked worktrees. Pack validation now commits the
generated baseline through the real pre-commit hook, creates a linked worktree,
proves both worktrees resolve the same executable `pre-commit` and `pre-push`
shims, executes both shims from the linked worktree, and removes the worktree
through Git.

## Commands and actual results

### Canonical pack validation

```bash
just validate
```

Final result: passed.

- Pack tests: 240 passed with 22 expected warnings in 46.00s.
- Template cleanliness and complete Jinja rendering: passed.
- Generated bootstrap: resolved 23 packages, installed 22 packages, installed
  prek 0.4.10 shims at `.git/hooks/pre-commit` and `.git/hooks/pre-push`, and
  passed the generated quality gate.
- Generated quality gate: Ruff format/lint, BasedPyright (0 errors, 0 warnings,
  0 notes), architecture, documentation, both import contracts, diagram sync,
  and LikeC4 validation all passed.
- Generated tests: 145 passed, 7 declared dormant variants skipped, 3 opt-in
  session tests deselected in 9.06s, with 93.44% branch coverage.
- The bootstrapped baseline passed every installed pre-commit hook.
- Linked-worktree hook-path and executable-shim checks passed. The staged-file
  pre-commit probe passed, and the ref-fed pre-push probe passed every hook,
  including the full quality gate. Git worktree cleanup passed.
- Previous-release and generated-recipe Copier update acceptance: 2 passed in
  23.38s.

Two earlier full runs exposed defects before the final pass:

- The first reached the new real baseline commit and failed because
  `.vscode/settings.json` contained JSONC comments rejected by `check-json`,
  while `end-of-file-fixer` added the missing newline to `CLAUDE.md`. The
  canonical template files and a focused regression test were corrected.
- The second passed bootstrap, the generated gate, the real commit hooks, and
  linked-worktree verification, then failed temporary cleanup with
  `OSError: [Errno 66] Directory not empty`. Validation now removes the linked
  worktree with `git worktree remove --force` before temporary-directory
  cleanup.

### Focused development checks

```bash
uv run --no-project --python 3.14 --with pytest==9.1.1 \
  --with copier==9.17.0 --with grimp==3.15 \
  pytest -q tests/test_instantiate.py::test_init_bootstraps_before_first_commit_and_hooks_cover_worktrees

uv run --no-project --python 3.14 --with pytest==9.1.1 \
  --with copier==9.17.0 --with grimp==3.15 \
  pytest -q tests/test_instantiate.py::test_init_stops_before_commit_and_github_when_bootstrap_fails

uv run --no-project --python 3.14 --with pytest==9.1.1 \
  --with copier==9.17.0 --with grimp==3.15 \
  pytest -q tests/test_instantiate.py::test_generated_baseline_files_pass_data_and_eof_hooks

uvx --from ruff==0.15.21 ruff check \
  instantiate.py scripts/validate_pack.py \
  tests/test_instantiate.py tests/test_update_roundtrip.py
```

Final focused results: each named pytest test passed; Ruff reported
`All checks passed!`.

## Tests added or updated

- CLI initialization proves `just bootstrap` runs after `git init` and before
  the first commit.
- Bootstrap failure proves init returns non-zero with no baseline commit and
  that a PATH-stubbed `gh` is never invoked.
- A real `git worktree add` proves commit and pre-push shim paths are shared and
  executable.
- Generated baseline data proves VS Code settings are strict JSON and
  `CLAUDE.md` ends with a newline.
- GitHub CLI tests retain PATH-stubbed `gh` and now use a PATH-stubbed bootstrap
  command, so unit tests remain local and network-free.
- The generated-tree digest and workspace-member delta reflect the synchronized
  downstream README.
- The update-roundtrip fixture uses an annotated `v0.2.1` candidate so Copier
  selects it over the existing annotated `v0.2.0` release tag.

## Remaining risks and portability notes

- Default init now performs dependency resolution, LikeC4 validation, and the
  complete generated test suite, so it requires the documented `uv`, `just`,
  Bun, Git, and network prerequisites and takes longer than generation alone.
- `--no-git` remains a deliberate generation-only mode and therefore cannot
  install prek hooks.
- Linked worktrees in the same local repository share the installed Git shims.
  A fresh clone has its own Git common directory and must run `just bootstrap`.
- Prek intentionally refuses to overwrite a global or system
  `core.hooksPath`; users with that configuration must move it to repository or
  worktree scope before init can install the shims.
- First dependency resolution and LikeC4 validation require network access.
