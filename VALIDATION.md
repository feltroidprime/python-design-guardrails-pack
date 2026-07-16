# Validation record — 2026-07-16

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just
1.56.0, Bun 1.3.9, Git 2.55.0, GitHub CLI 2.96.0, Copier 9.17.0, and
pytest-xdist 3.8.0. The template was intentionally dirty with the change under
validation, so Copier emitted 21 honest `DirtyLocalWarning` instances during
the pack test phase.

## Change validated

Generated repositories contain an opt-in Claude Code and Codex session-evidence
route backed by private package `session-profiler-optimizer` at immutable commit
`6ace879e8642777658576a47e0f53b32a1ddc0f7`. The package is injected only by
`just session-log` and `just session-e2e`; it is absent from project dependency
groups and the lockfile, so baseline bootstrap, `just check`, and generated CI
need no cross-repository credential.

The lazy compatibility facade preserves the package's `convert_session` API.
Consumer tests pin ATIF-v1.7, the public artifact set, raw-byte preservation,
deterministic replay, and the exact manifest checks: content hashes, coverage,
metric coherence, orphan-blob reachability, profile rows, and subagent
references. Real-session E2E requires five primary sessions per available agent
and samples one from each byte-size quintile.

The benchmark Git command configuration also disables detached auto-gc in
ephemeral arm repositories. This prevents Git from recreating `.git/info`
after workspace cleanup.

## Commands and actual results

### Canonical pack validation

```bash
just validate
```

Final result: passed.

- Pack tests: 230 passed with 21 expected warnings in 40.41s.
- Template cleanliness and complete Jinja rendering: passed.
- Fresh baseline `uv sync --all-groups`: resolved 23 packages without fetching
  the private profiler.
- Generated gate: Ruff format/lint, BasedPyright (0 errors, 0 warnings, 0
  notes), architecture, documentation, both import contracts, diagram sync,
  and LikeC4 validation all passed.
- Generated tests: 58 passed, 3 intentionally dormant command-kind cases
  skipped, 3 opt-in session tests deselected, and branch coverage was 91.19%.
- Deterministic downstream repair probe: passed with no canonical drift.
- Copier update acceptance: 2 passed in 19.86s.

The corrective loop also recorded these expected red states before the final
run:

- `just validate` failed at
  `test_generated_justfile_has_one_routine_gate_and_one_private_e2e_route`
  with `assert 0 == 1` after the private package moved to `uv run --with`; the
  stale recipe assertion was updated.
- Two subsequent `just validate` runs reached the downstream gate and then
  reported `VALIDATION FAILED at step: downstream repair probes` for the lazy
  facade/E2E sources; their canonical formatting was synchronized before the
  passing run.

### Opt-in private consumer

From a fresh generated `orchard-billing` repository:

```bash
uv sync --all-groups
just session-e2e
```

The baseline sync resolved 23 packages without the private dependency.
`just session-e2e` then executed:

```bash
uv run --with "$SESSION_PROFILER_DEPENDENCY" pytest -q -m session_e2e \
  -o addopts="--strict-config --strict-markers --disable-socket" tests/e2e
```

Result: 3 passed in 1.16s. The run converted five Claude and five Codex primary
sessions plus the deterministic generated consumer fixture.

## Tests added or updated

- Generator tests require the private pin to occur once in the generated
  justfile, remain absent from baseline dependencies, and drive both opt-in
  recipes.
- The consumer contract requires the exact manifest check vocabulary,
  ATIF-v1.7, raw byte equality, the complete artifact set, and byte-identical
  repeated conversion.
- Real-session E2E uses the exported `AgentType`, samples exactly five
  quantiles, skips an agent only at zero sessions, and fails clearly for one to
  four sessions.
- The existing benchmark workspace-removal behavior test covers the
  `gc.auto=0` cleanup regression.

## Remaining risks and portability notes

- Opt-in session commands require network access plus authenticated read access
  to the private package (`gh auth setup-git`). Baseline bootstrap and CI do not.
- Harbor's transcript conversion methods remain private. Any package-pin update
  must replay its owned fixtures and real-session quintiles before this pin
  moves; that independent package suite was not rerun by the pack command above.
- Native logs may contain source, prompts, tool output, or echoed credentials.
  Output is Git-ignored and owner-only on POSIX; Windows relies on the containing
  directory's access controls.
- The E2E sample is deliberately random and opt-in. A newly selected failure is
  native-format drift evidence, not a reason to weaken the consumer contract.
- First baseline dependency resolution and LikeC4 validation require network
  access.
