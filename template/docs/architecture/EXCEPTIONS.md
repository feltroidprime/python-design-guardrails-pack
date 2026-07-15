# Architecture exception ledger

## Active exceptions

### ADR-0003 — subprocess execution at the mandatory CLI process seam

- Files/diagnostics: `tests/integration/test_cli.py` and
  `tests/integration/test_cli_contract.py`, Ruff S603 on their single
  `subprocess.run` helper calls.
- Owner: repository maintainers.
- Reason: the CLI contract must observe the installed process with detached
  stdin, real streams, exit status, isolated working directory, and timeout;
  an in-process substitute cannot prove those properties.
- Risk: a future test could pass untrusted arguments to the helper.
- Revisit trigger: the test runner provides a typed process fixture that Ruff
  can recognize as safe, or either helper accepts input outside closed test
  cases.
- Removal criteria: replace both helper calls with an equally complete process
  seam that needs no S603 suppression.

### ADR-0003 — argparse override parameter retains its framework name

- File/diagnostic: `src/*/adapters/inbound/cli.py`, ARCH019 on the `file`
  parameter of `_ContractParser._print_message`.
- Owner: repository maintainers.
- Reason: this protected argparse override must retain the base method's
  keyword-compatible parameter name and `SupportsWrite[str]` type; it is an
  output stream, not a filesystem location.
- Risk: readers could mistake the name for a path despite the precise type.
- Revisit trigger: argparse exposes a public injected-output hook or the parser
  boundary is replaced under a superseding ADR.
- Removal criteria: delete the override or use a framework API whose parameter
  name does not conflict with Path discipline.

### ADR-0003 — broad translation at the CLI process boundary

- File/diagnostic: `src/*/adapters/inbound/cli_runtime.py`, Ruff BLE001 on the
  outer `Exception` translation boundary.
- Owner: repository maintainers.
- Reason: the versioned process contract must hide otherwise unclassified
  internal failures behind exit 70 and a stable envelope. Known domain and
  dependency failures are translated more narrowly first; explicit `--debug`
  keeps exit 70 while printing the captured traceback.
- Risk: a programmer defect is translated during normal CLI execution instead
  of immediately surfacing as an uncaught exception.
- Revisit trigger: Python gains a narrower common exception family for
  application failures, or the process supervisor owns this translation.
- Removal criteria: preserve stable unexpected-failure output and exit
  semantics without a broad boundary catch.

Each exception must include:

- ADR identifier;
- exact files/imports/diagnostics covered;
- owner;
- reason the normal rule cannot currently hold;
- risk introduced;
- expiry date or objective revisit trigger;
- removal criteria.

Suppressions in code must use a narrow code and include `ARCH-EXCEPTION: ADR-XXXX`.
