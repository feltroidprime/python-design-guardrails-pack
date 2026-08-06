# Architecture exception ledger

Every suppression in code must name a narrow diagnostic and carry an
`ARCH-EXCEPTION: ADR-NNNN` marker. Every entry below must state the ADR, the
exact scope, the owner, the reason, the risk, an objective revisit trigger, and
the removal criteria.

## Active exceptions in code

### ADR-0008 — the pack tests read the tracked tree through `git`

- Files and diagnostic: `pack/tests/test_gate_definition.py` and
  `pack/tests/unit/scripts/test_ownership.py`, Ruff S603.
- Owner: repository maintainers.
- Reason: the ownership predicate answers for a real tracked tree or it answers
  for nothing, and `git ls-files -z` is the only source of that tree. The
  command is a fixed constant, and no caller supplies an argument.
- Risk: a later edit could pass caller input to the same helper.
- Revisit trigger: the test runner supplies a typed process fixture that Ruff
  accepts as safe.
- Removal criteria: read the tracked tree through a library call that needs no
  suppression.

## Active narrowings in policy

A narrowing lives in a config file rather than in a comment, so it carries no
marker. It must still be recorded here.

### `BLE001` for the router

- File and diagnostic: `_foundation/router.py`, Ruff BLE001, through a
  directory glob in `pack/configs/ruff.toml`.
- Owner: repository maintainers.
- Reason: the last row of the router's exception table reads "anything else",
  and the router answers it with one `unexpected_failure` envelope and exit 70.
  A handler that catches every remaining exception is the rule in that one
  module, and it is why a capability never selects an exit code.
- Risk: a programming defect is translated into an envelope during an ordinary
  run.
- Revisit trigger: the standard library gains a narrower common failure class
  that covers the same row.
- Removal criteria: keep the stable unexpected-failure output without a broad
  catch.

`DESIGN_GUARDRAILS.md` at the repository root states the same narrowing beside
every other deliberate loosening.
