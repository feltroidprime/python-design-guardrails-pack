# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

This merge combines the macOS hook fix from PR #78 with the root-suite
performance work already on `main`.

- Generated `prek.toml` pins Python-language hooks to Python 3.14, matching the
  generated repository's interpreter and syntax contract.
- The initializer suppresses Copier's expected `DirtyLocalWarning` when it
  renders current editable-worktree changes; unrelated warnings remain visible.
- The root pytest session removes an invoking hook's repository-local Git
  variables so nested Git fixtures cannot target the pack checkout.
- Four representative shape tests now prepare their active capability directly
  through the real `repoctl` CLI and run one complete generated gate. The one
  canonical 19-step N0 → N1 → N2 walk remains unchanged.
- `just test` runs the canonical walk alone, six `repository_gate` tests across
  five workers, and the complementary lightweight tests across five workers.
  The pre-push hook advertises a seven-minute warm-cache budget.

## Focused and performance evidence

Before merging, the hook branch passed:

- **2 focused hook/warning regressions** in 2.33 seconds;
- the complete generator module, **56 tests**, in 42.45 seconds with uncaught
  `DirtyLocalWarning` treated as an error;
- the injected Git-hook-context reproduction, **57 tests**, in 11.69 seconds;
- a real `python-repo init ... --no-github` smoke, including the generated
  quality gate and every initial-commit hook;
- its canonical `just validate`, including **245 root tests** and generated
  gates of **127 passed, 1 skipped, 3 deselected** at **95.65% coverage**.

Profiling on `main` found that three repeated generated gates consumed 183.03
of a representative shape test's 195.18 seconds (93.8%). After removing those
redundant lifecycle walks, the external-integration shape took 65.14 seconds.
A warm-cache root run completed all 244 then-current tests in 370.44 seconds
(6:10), versus the 541.04-second (9:01) baseline: 31.5% faster.

The scheduling selectors were collected independently before merging:

- canonical recursive walk: **1** node;
- `repository_gate` phase: **6** nodes;
- complementary lightweight phase: **237** nodes;
- complete then-current suite: **244** nodes, with no overlap or omission.

## Merged-state validation

The resolved merge is validated with:

```bash
just test-fast
just validate
```

`just test-fast` passed **14 tests** in 6.33 seconds after Ruff reported
**154 files already formatted** with no lint violations. Direct collection
selected **6/245** `repository_gate` tests and **238/245** complementary tests;
with the separately selected canonical test, all 245 nodes are covered exactly
once.

The canonical `just validate` command passed end to end:

- the root phases passed **1**, **6**, and **238** tests in 401.12, 291.01,
  and 36.94 seconds respectively;
- template cleanliness, fresh generation, complete Jinja rendering, bootstrap,
  and the missing-hook repair probe passed;
- BasedPyright reported **0 errors and 0 warnings**; ownership, architecture,
  documentation, proof-contract, bounded CrossHair, and Import Linter checks
  passed;
- the two visible generated gates each passed **127 tests, 1 skipped,
  3 deselected**, in 80.00 and 57.80 seconds, with **95.65% coverage**;
- the generated initial commit passed every prek hook under the Python 3.14
  policy;
- tracked syntax rejection, clean and dirty doctor probes, and linked-worktree
  pre-commit and pre-push probes passed.

The root timings are a loaded-host correctness sample, not the warm-cache
performance measurement: unrelated trading benchmarks were concurrently using
multiple CPUs. The syntax and dirty-tree failures printed during validation are
deliberate fault-injection probes.

## Remaining risks and portability notes

- Full validation is executed on Linux x86_64. The reported hook failure was
  macOS arm64; the fix uses prek's platform-independent Python toolchain
  configuration, but this environment cannot rerun the final acceptance suite
  on macOS.
- Existing generated repositories retain their old `prek.toml`; regenerate or
  add `default_language_version.python = "python3.14"`, then reinstall hooks
  with `uv run prek install -f`.
- The seven-minute performance budget assumes warm caches without another
  CPU-intensive suite. Concurrent pushes or unrelated benchmarks can erase the
  wall-clock gain.
- The canonical recursive walk remains an irreducible roughly three-minute
  floor because it intentionally executes the complete lifecycle and generated
  quality gates.
