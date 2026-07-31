# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #70 records the deterministic test that kills each of SPEC-0001's
fourteen mandatory equivalent mutants.

- A machine-readable catalog preserves each specification number, stable local
  identifier, exact mutation text, deterministic mechanism, evidence node, and
  focused command.
- A read-only audit fixes the catalog to the specification's exact order and
  wording, rejects missing, duplicated, or renamed entries, limits mechanism
  names to deterministic categories, and confirms every command names a
  pytest-collectable function in the pack or generated template.
- The existing guard, contract, Hypothesis-property, and proof-gate tests remain
  the executable evidence. No second mutation runner, source rewriter,
  production check, template behavior, or recursive harness change was added.

## Commands and actual results

```bash
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q tests/mutations
just check
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q \
  tests/test_proof_guard.py::test_pure_contracted_function_requires_crosshair_evidence
just test
just validate
```

The TDD red run failed during collection because
`tests/fixtures/mutation_catalog.json` did not exist. The final focused catalog
audit passed **15 tests** in 0.03 seconds. The focused existing CrossHair
coverage mutation test passed **1 test** in 0.06 seconds. Root Ruff reported
**153 files already formatted** and no lint violations.

The independent `just test` run passed **242 tests** with 20 dirty-template
warnings in 537.07 seconds.

The canonical `just validate` command passed end to end:

- root Ruff repair/check was stable across 153 files, and the root suite passed
  **242 tests** with 20 dirty-template warnings in 556.58 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- both generated gates passed **127 tests, 1 skipped, 3 deselected**, first in
  32.65 seconds and then in 35.28 seconds, with **95.65% coverage** (90%
  required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The successful canonical root suite took 556.58 seconds, within the
  documented ten-minute warm-cache budget but with limited headroom for later
  recursive shape fixtures.
- The catalog audit checks exact metadata and pytest-collectable evidence
  nodes; it deliberately relies on the canonical root/generated suites to
  execute those existing killers instead of wrapping them in another runner.
- The remaining composition, generated update-preservation, and agent-workflow
  cases are owned by issues #71–#73.
