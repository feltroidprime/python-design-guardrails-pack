# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

The root suite was profiled and reorganized without changing the generated
product or deleting any collected test.

- A representative shape test took 195.18 seconds. Temporary timing
  instrumentation attributed 183.03 seconds (93.8%) to three complete
  generated-repository gates: bootstrap at 56.46 seconds, the first
  `just check` at 61.53 seconds, and the second at 65.04 seconds.
- Four shape tests were incorrectly reusing the complete N0 → N1 → N2
  acceptance walk. They now prepare the shape directly through the real
  `repoctl` CLI, activate it, and run one complete generated gate. The one
  canonical 19-step recursive walk remains unchanged.
- Shape-specific assertions remain load-bearing. Pure-library, stateful, and
  external-integration cases assert their required active state and boundaries;
  the CLI case still exercises activation, a detached process, retirement,
  runtime-index removal, and byte preservation.
- `just test` now runs the canonical walk alone, the six
  `repository_gate`-marked shape/scale tests across five workers, and the
  complementary lightweight set across five workers. Positive and negative
  marker selection make the phases disjoint and exhaustive by construction.
- The pre-push hook now advertises a seven-minute warm-cache budget. No file
  under `template/` changed.

## Commands and actual results

The final fast gate was:

```bash
just test-fast
```

Ruff reported **154 files already formatted** with no lint violations, and the
focused suite passed **14 tests** with two expected dirty-template warnings in
3.12 seconds.

Marker collection was checked directly:

```bash
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest --collect-only -q -m repository_gate tests \
  --deselect tests/recursive/test_recursive_generation.py::test_recursive_walk_executes_the_specification_through_repoctl

uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest --collect-only -q -m "not repository_gate" tests \
  --deselect tests/recursive/test_recursive_generation.py::test_recursive_walk_executes_the_specification_through_repoctl
```

The marked phase collected **6/244** tests and the complement collected
**237/244**. Together with the separately selected canonical test, all 244
nodes are covered exactly once, with no overlap or omission.

The isolated external-integration shape improved from **195.18 seconds** to
**65.14 seconds** while retaining one complete generated gate. The
representative warm-cache `just validate` root phases passed as follows:

- canonical recursive walk: **1 passed** in **188.08 seconds**;
- repository-gate matrix: **6 passed** in **159.18 seconds**;
- lightweight complement: **237 passed** in **23.18 seconds**.

That is **370.44 seconds (6:10)** for all 244 root tests, versus the measured
baseline of **541.04 seconds (9:01)**: 170.60 seconds, or 31.5%, faster.

The required final command after correcting the documented budget was:

```bash
just validate
```

It passed end to end. Two unrelated trading benchmarks were consuming CPU
during this final run, so its root phase timings were 283.97, 227.67, and
30.01 seconds rather than the warm-cache performance sample above. The run
still passed all **244 root tests** exactly once, with 21 expected
dirty-template warnings.

The final generated-repository validation also passed:

- template cleanliness, fresh generation, complete Jinja rendering, bootstrap,
  and the missing-hook repair probe passed;
- BasedPyright reported **0 errors and 0 warnings**;
- ownership, architecture, documentation, proof-contract, bounded CrossHair,
  and Import Linter checks passed;
- the two visible generated gates each passed **127 tests, 1 skipped,
  3 deselected**, in 55.68 and 49.98 seconds, with **95.65% coverage**
  (90% required);
- tracked syntax rejection, clean and dirty doctor probes, and linked-worktree
  pre-commit and pre-push probes passed.

Two earlier `just validate` attempts were deliberately interrupted after a
separate worktree started the old pre-push suite concurrently. Their canonical
walks had inflated to 276.67 and 302.13 seconds. The syntax and dirty-tree
failures printed by completed validation runs are deliberate fault-injection
probes, not validation failures.

An experiment that enabled bytecode-cache writes made the canonical walk
slower (234.45 versus 183.27 seconds in that comparison), so it was fully
reverted.

## Reviews

The final structure passed concurrent Spec, Standards, and thermo-nuclear code
quality reviews. Reviewers independently verified the 1 + 6 + 237 partition,
the retained generated gates, and the absence of path-list duplication,
coverage erosion, or new abstraction/spaghetti growth.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The seven-minute budget describes a warm-cache run without another
  CPU-intensive suite. Concurrent pushes or unrelated benchmarks can erase the
  wall-clock gain even though the amount of test work is reduced.
- The canonical recursive walk remains an irreducible roughly three-minute
  floor because it intentionally executes the complete lifecycle and its
  generated quality gates.
