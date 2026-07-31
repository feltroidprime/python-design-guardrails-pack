# Validation record — 2026-07-31

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.1,
and prek 0.4.11.

## Change validated

Issue #71 moves the update-preservation scenario from a copied fixture to a
capability created by the generated repository's real CLI.

- The test invokes detached `python -m repoctl capability plan` and
  `capability apply` commands for one representative capability.
- It customizes every `create_product_seed` path declared by that plan, hashes
  every customized file, and proves a normal synthetic foundation update
  preserves all bytes.
- The existing product-overwrite mutant still proves the oracle is
  fault-sensitive, while a source audit rejects the former hand-seeded fixture
  path and symbol.
- No generated template or recursive harness behavior changed.

## Commands and actual results

```bash
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q \
  tests/test_update_preservation.py::test_update_scenario_no_longer_references_the_hand_seeded_fixture
uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  --with "icontract>=2.7.3" \
  pytest -q tests/test_update_preservation.py
just check
just validate
```

The TDD red anti-fixture test failed as intended while the old fixture path
remained. The final focused file passed **4 tests** in 5.13 seconds, including
the normal update and deliberate overwrite-mutant branches. An initial
`just check` identified the anti-fixture string construction as Ruff FLY002;
after correction, root Ruff reported **153 files already formatted** and no
lint violations.

The canonical `just validate` command passed end to end:

- root Ruff repair/check was stable across 153 files, and the root suite passed
  **243 tests** with 20 dirty-template warnings in 536.34 seconds;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- both generated gates passed **127 tests, 1 skipped, 3 deselected**, first in
  33.31 seconds and then in 32.04 seconds, with **95.65% coverage** (90%
  required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The successful canonical root suite took 536.34 seconds, within the
  documented ten-minute warm-cache budget but with limited headroom for later
  recursive shape fixtures.
- The scenario exercises the single representative capability required by
  SPEC-0001 §20.5 and intentionally depends on the public plan operation kind
  `create_product_seed`.
- The remaining composition and agent-workflow cases are owned by issues
  #72–#73.
