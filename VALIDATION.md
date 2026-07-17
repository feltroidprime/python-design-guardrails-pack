# Validation record — 2026-07-17

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just
1.56.0, Bun 1.3.9, Git 2.55.0, GitHub CLI 2.96.0, Copier 9.17.0, and
pytest-xdist 3.8.0. Copier emitted 25 expected `DirtyLocalWarning` instances
because the canonical changes were intentionally uncommitted during the pack
tests.

## Change validated

The generated repository harness now fails early on mechanically invalid local
state:

1. `just check` resolves Git's common hooks directory and verifies executable
   prek pre-commit and pre-push shims before any other check;
2. missing or invalid shims are repaired with exactly
   `uv run prek install -f`, while an impossible repair prints that command as
   the first diagnostic line;
3. every tracked `*.py` file is syntax-compiled before repair steps, including
   files that no import or test reaches;
4. `just doctor` emits six stable readiness statuses plus one verdict for hooks,
   working-tree state, local default-branch synchronization with `origin`,
   GitHub CLI authentication, `uv sync --check`, and Python version.

The doctor skips missing remotes and absent or offline GitHub access with a
warning. Any local defect or reachable external-state failure produces a
`fail` status and a non-zero verdict. Its network checks have two-second
timeouts, and pack validation rejects either the clean or faulted probe if it
takes five seconds or longer.

## Commands and actual results

### Canonical pack validation

```bash
just validate
```

Final result: passed.

- Pack tests: 244 passed with 25 expected warnings in 48.26s.
- Template cleanliness and complete Jinja rendering: passed.
- Generated bootstrap: resolved 23 packages, installed 22 packages, installed
  prek 0.4.10 shims at `.git/hooks/pre-commit` and `.git/hooks/pre-push`, and
  passed the generated quality gate.
- Generated quality gate: Ruff format/lint, BasedPyright (0 errors, 0 warnings,
  0 notes), architecture, documentation, both import contracts, diagram sync,
  LikeC4 validation, and all tests passed. The test result was 145 passed,
  7 declared dormant variants skipped, 3 opt-in session tests deselected, and
  93.44% branch coverage.
- After both installed prek shims were deleted, `just check` reinstalled them
  and passed the complete gate. Both repaired shims were executable in Git's
  common hooks directory.
- A tracked, un-imported file containing invalid syntax was rejected by the
  new tracked-Python syntax step before repair or acceptance work.
- On the committed clean baseline, `just doctor` reported four `ok` statuses,
  two expected offline/no-remote warnings, no failures, and exited zero. After
  one untracked file was planted, it named the dirty working tree, reported one
  failure, and exited non-zero. Both probes completed within the enforced
  five-second budget.
- Linked-worktree hook-path and executable-shim checks passed. The staged-file
  pre-commit probe passed, and the ref-fed pre-push probe passed every hook,
  including the full quality gate. Git worktree cleanup passed.
- Previous-release and generated-recipe Copier update acceptance: 2 passed in
  23.18s.

### Focused development checks

```bash
uv run --no-project --with copier==9.17.0 --with pytest==9.0.2 pytest -q \
  tests/test_instantiate.py::test_generated_doctor_reports_green_then_detects_a_dirty_working_tree \
  tests/test_instantiate.py::test_generated_justfile_has_one_routine_gate_and_one_private_e2e_route

uv run --no-project --python 3.14 --with copier==9.17.0 \
  --with pytest==9.1.1 pytest -q \
  tests/test_instantiate.py::test_default_generation_matches_recorded_output

just test
```

Final focused results: the doctor/justfile pair passed (2 passed, one expected
dirty-template warning in 3.14s); the generated-tree digest passed after its
intentional update; and the checkpoint-2 pack suite passed with 243 tests and
25 expected warnings in 49.91s before the documentation assertion brought the
canonical final suite to 244 tests.

## Tests added or updated

- A PATH-stubbed hook-install failure proves the literal recovery command is
  the gate's first diagnostic line.
- A tracked but un-imported Python file proves syntax errors fail before any
  deterministic repair can hide or bypass them.
- A bootstrapped generated repository proves `just doctor` has seven stable
  output lines and exits zero when its available checks are green.
- The same repository receives one untracked file and proves the doctor names
  the working-tree failure, emits a failing verdict, and returns non-zero.
- End-to-end pack validation deletes and repairs both real prek shims, injects
  and cleans the tracked syntax fault, and runs the doctor in clean and dirty
  states under its runtime budget.
- The generated-file inventory, justfile recipe contract, and deterministic
  tree digest include the new doctor implementation and documentation.

## Remaining risks and portability notes

- Default initialization still performs dependency resolution, LikeC4
  validation, and the complete generated test suite, so it requires the
  documented `uv`, `just`, Bun, Git, and network prerequisites and takes longer
  than generation alone.
- `just doctor` deliberately warns instead of failing when no `origin` exists,
  `gh` is absent, GitHub is offline, or a template variant intentionally omits
  standalone hook or Python-version policy. Those skipped checks remain human
  review items before an actual publication.
- Reachable but invalid GitHub authentication and a reachable but divergent or
  broken default branch are failures. The two network probes are independently
  bounded at two seconds, so a severely degraded network can consume most of
  the five-second total budget.
- `uv sync --check` runs offline and does not repair the environment. Run
  `just bootstrap` or `uv sync --all-groups` when it reports a failure.
- Linked worktrees in the same local repository share installed Git shims. A
  fresh clone has its own Git common directory; `just check` now repairs its
  missing shims automatically when prek policy is enabled.
- Prek intentionally refuses to overwrite a global or system
  `core.hooksPath`; users with that configuration must move it to repository or
  worktree scope before the generated gate can install the shims.
