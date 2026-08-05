# Architecture exception ledger

## Active exceptions

### ADR-0002 — subprocess execution at the repository-control process seam

- Files/diagnostics: detached-process helpers under `tests/repoctl/`, Ruff
  S603.
- Owner: repository maintainers.
- Reason: control commands must be observed through real stdin, streams, exit
  status, and isolated working directories.
- Risk: a future test could pass untrusted arguments to a helper.
- Revisit trigger: the test runner supplies a typed process fixture that Ruff
  recognizes as safe.
- Removal criteria: replace the helpers with an equally complete seam that
  needs no S603 suppression.

### ADR-0002 — argparse override keeps its framework parameter name

- File/diagnostic: `repoctl/modules/repository_generation/adapters/inbound/cli.py`,
  ARCH019 on `_ContractParser._print_message`.
- Owner: repository maintainers.
- Reason: the protected argparse override must retain the base method's
  keyword-compatible `file` parameter; it is an output stream, not a path.
- Risk: readers could mistake the name for a filesystem location.
- Revisit trigger: argparse exposes a public injected-output hook.
- Removal criteria: delete the override or use an API without the conflicting
  parameter name.

### ADR-0002 — broad translation at the repository-control process boundary

- File/diagnostic: `repoctl/modules/repository_generation/adapters/inbound/cli.py`,
  Ruff BLE001.
- Owner: repository maintainers.
- Reason: the process protocol translates unexpected failures into one stable
  machine envelope; explicit debug output preserves diagnostic access.
- Risk: a programming defect is translated during ordinary CLI execution.
- Revisit trigger: the supervisor gains a narrower common failure boundary.
- Removal criteria: preserve stable unexpected-failure output without a broad
  catch.

Each exception must include an ADR identifier, exact scope, owner, reason,
risk, an objective revisit trigger, and removal criteria. Suppressions in code
must use a narrow diagnostic and `ARCH-EXCEPTION: ADR-XXXX` marker.
