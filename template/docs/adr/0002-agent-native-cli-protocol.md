# ADR-0002: Agent-native CLI protocol and exhaustive command catalog

- Status: accepted
- Date: 2026-07-15
- Owners: repository maintainers
- Revisit trigger: a command needs a behavior outside the five catalog kinds,
  or a consumer needs a breaking schema or exit-classification change

## Context and forces

The generated example previously exposed `add` and `list` through hand-written
argument matching and human prose. Nothing forced a future command to be
discoverable, non-interactive, bounded, machine-readable, retry-explicit, or
tested at the real process boundary. Exact help text and parser internals must
remain replaceable, while the automation behavior must not drift.

## Decision

`adapters/inbound/cli_catalog.py` is the only command registration surface.
It owns closed command identities and kinds, purposes, automation examples,
output modes, argument declarations, retry policy, and bounding policy.
`adapters/inbound/cli.py` is the private argparse boundary and derives its
parser from that catalog. It immediately produces typed requests consumed by
`adapters/inbound/cli_runtime.py`; application and domain code never receive
argparse objects.

Machine success and failure documents use schema version `1.0`. Success
contains `schema_version`, `command`, `data`, and `metadata`. Failure contains
`schema_version`, `command`, and an `error` with stable `code`, editable human
`message`, `retryable`, and corrective `hint`. Exit classes are fixed at 0
(success/help), 2 (syntax), 3 (permanent rejection), 4 (temporary dependency),
and 70 (unexpected failure). Breaking schema or exit changes require a new ADR
and protocol version. The same applies to removing or renaming a command,
changing its kind, or weakening a required policy; adding optional data within
the existing envelope does not. `PROTOCOL_DECISION` identifies the accepted
ADR, and unit tests pin the existing identities, kinds, policies, schema, and
exit classes so those changes cannot be incidental.

JSON is the default for data-bearing commands; human output is selected
explicitly. The catalog owns that default once, capabilities publishes it, and
the parser consumes the same field. Query page bounds likewise live only in
their query policy. Queries use positive default and maximum limits, stable
ordering, and typed continuations; wire-format strings are confined to the
inbound adapter. The application and repository receive the bound, rather than
truncating an unbounded rendered result. Mutations declare replay safety; the
example `add` is explicitly non-idempotent and returns an operation ID.
Unexpected failures are hidden unless the cataloged `--debug` option is used.

`tests/contract/cli_contract_cases.py` independently declares one closed
behavioral case per command. Exact catalog/case completeness plus universal
process tests make a missing, duplicate, or stale case fail. Query, mutation,
streaming, interactive/bootstrap, and bulk/export case variants require their
kind-specific fixtures; future-kind cases reject empty or disconnected control
declarations at construction. Streaming cases compare isolated filtered and
terminated runs with an unfiltered, over-limit baseline so ignored controls
cannot pass.
Invalid scenarios pin their exact error and exit classification, compare an
independent CLI readback before and after failure, and make bulk destinations
observable as absent artifacts. The architecture guard rejects inbound prompt
calls, uncontrolled exits, CLI-framework leakage, and any command name or alias
not drawn directly from the catalog, including indirect registration and
unpacked parser keywords (ARCH021–024).

The two `S603` suppressions in the CLI integration suites are accepted because
those tests must execute the real installed module with detached stdin, an
isolated working directory, captured streams, and a timeout. Arguments are
closed test literals, never untrusted input.

## Alternatives considered

- **Keep hand-written matching and add examples.** Rejected: examples do not
  make future command registration or contract coverage exhaustive.
- **Snapshot argparse help and JSON text.** Rejected: wrapping, wording, key
  order, and parser implementation are not compatibility surfaces.
- **Introduce a CLI framework or plugin registry.** Rejected: argparse and a
  closed in-repository catalog satisfy the requirement without a dependency or
  dynamic registration path.
- **Automatically retry mutations.** Rejected: the application cannot infer
  idempotence, and ambiguous non-idempotent outcomes must remain visible.

## Consequences

### Positive

- A green quality gate proves every exposed command has an independent case
  and passes the universal automation contract at the process seam.
- Capability discovery, parser construction, and command help share one source
  without coupling tests to argparse internals or prose layout.
- Bounds and retry semantics are visible to both agents and maintainers.

### Negative / cost accepted

- The example carries a catalog, protocol serializer, runtime translator, and
  a larger integration suite for only three commands.
- Each new command requires both a catalog entry and an independent typed case.

### Risks and mitigations

- *The catalog becomes a framework:* its variants remain closed and concrete;
  new abstraction axes require this ADR to be superseded.
- *Generic contracts overclaim business correctness:* command-specific tests
  still own domain semantics; the contract kit proves process properties only.
- *Broad failure translation hides defects:* `--debug` deliberately restores
  tracebacks, while exit 70 keeps unattended stdout and stderr stable.

## Validation

The generated quality gate runs exact catalog/case completeness, process
success and failure for every command, help discovery, JSON structure,
stdout/stderr isolation, detached stdin and timeouts, query continuation,
mutation replay/readback, invalid-case effect readback, effectful streaming
controls, explicit human output, and the ARCH021–024 fitness functions. Pack
validation instantiates a fresh repository and runs that gate.

## Migration and rollback

Existing `add` and `list` invocations keep their command names. Automation must
consume JSON by default; humans select `--format human`. Rolling back requires
removing the catalog, protocol, cases, ARCH021–024, and this ADR together, and
would intentionally abandon the agent-native guarantee.

## Removal / supersession criteria

Supersede this ADR when the protocol major version, exit classes, command-kind
model, or parser framework changes. Never rewrite the accepted version in
place; retain compatibility or document and version the break.
