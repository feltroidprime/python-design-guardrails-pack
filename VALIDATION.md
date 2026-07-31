# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #73 documents one canonical capability lifecycle in the conditional
downstream agent contract and checks every executable line against the
recursive acceptance walk that already exercises it.

- The workflow covers discovery, plan/apply, implementation and evidence,
  activation, regeneration, one focused proof, the full gate, retirement,
  regeneration, staging, and the full gate again.
- The recursive test extracts the marked command block, substitutes its two
  documented placeholders, and requires those commands to be an ordered
  subsequence of the existing invocation log. It does not run a second walk.
- The generated README links to the agent contract instead of duplicating the
  workflow.
- `DESIGN_GUARDRAILS.md` now maps the recursive acceptance walk, representative
  shape matrix, and mutation catalog to their executable evidence.

## Commands and actual results

```bash
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q \
  tests/test_docs_guard.py::test_template_documentation_passes_the_guard \
  tests/test_instantiate.py::test_generated_docs_guard_runs_and_passes \
  tests/test_instantiate.py::test_root_and_template_markdown_contain_no_removed_product_vocabulary

uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q \
  tests/recursive/test_recursive_generation.py::test_recursive_walk_executes_the_specification_through_repoctl

just check
just validate
```

The focused documentation checks passed **3 tests** with one expected Copier
dirty-template warning in 1.75 seconds. The focused real recursive walk passed
**1 test** with one expected warning in 183.27 seconds. Root Ruff reported
**154 files already formatted** and no lint violations.

The canonical `just validate` command passed end to end:

- root Ruff repair/check was stable across 154 files, and the root suite passed
  **244 tests** with 21 dirty-template warnings in 541.04 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- the first two visible generated gate executions each passed **127 tests,
  1 skipped, 3 deselected**, in 37.86 and 31.26 seconds, with **95.65%
  coverage** (90% required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit and pre-push probes passed. The linked
  pre-push hook reported its full quality gate passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The successful canonical root suite took 541.04 seconds, within the
  documented ten-minute warm-cache budget but with limited headroom.
- The extractor deliberately supports one shell command per line and the two
  documented placeholders. A future workflow syntax change must update the
  parser and recursive walk together.
- Activation flags assert that their named evidence forms exist; the workflow
  explicitly warns agents not to pass them speculatively.
