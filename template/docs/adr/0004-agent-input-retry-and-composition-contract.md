# ADR-0004: Agent input, retry, safety, outcome, and composition contract

- Status: accepted
- Date: 2026-07-16
- Owners: repository maintainers
- Revisit trigger: ordinary arguments are proposed for removal, a real
  destructive command is introduced, a second resource group needs a command
  tree, or stateful/API-only use makes an MCP surface materially useful

## Context and forces

ADR-0002 established a closed catalog, versioned machine envelopes, bounded
queries, retry metadata, detached process cases, and stable exit classes. It
did not make the input model itself a closed policy, and several published
policies described intent without proving the corresponding behavior.

Agents need constrained arguments without mandatory shell-quoted JSON,
explicit stdin behavior, safe retry facts, composable query output, and
discoverable recovery before execution. Those properties must survive command
growth without freezing help wording, JSON key order, or parser internals.

## Decision

This decision extends ADR-0002; it does not replace its envelopes, exit
classes, machine defaults, command names, or process seam. Protocol documents
remain schema `1.0`, while capability discovery advertises both governing
decisions. The additions are backward-compatible protocol 1.x metadata and
output modes. Removing an argument path, changing a default, renaming a
command, or reclassifying an exit requires a versioned break.

Every command declares an input policy. Ordinary typed positional arguments
and flags remain the primary automation path. Stdin is a closed choice among
forbidden, optional, and required; accepted stdin uses the documented `-`
marker. Structured input may later be added through a file or documented
stdin, but inline JSON cannot become the only path. ARCH025 rejects a catalog
entry without explicit argument-primary input. The independent input case also
requires a successful typed-argument process invocation; required-stdin
commands receive their declared payload while optional/forbidden commands run
with closed stdin. Structured-input fixtures are additive and cannot satisfy
that obligation. An accepted-stdin
case must name a payload-derived value and observe it in the command result or
an independent readback, so merely ignoring an open pipe cannot pass.

Removing the argument path requires a new ADR and checked-in comparative
evaluation. The experiment must fix tasks and success criteria and cover
representative weak and strong models, PowerShell and a POSIX shell,
correctness, retry behavior, token use, cost, and failure categories. No such
evaluation is required for this additive decision.

Catalog argument declarations own public value type, required/default state,
closed choices, repeatability, and sensitivity. The private argparse adapter
uses them to generate complete but wording-flexible help, and `capabilities`
publishes the same shapes without exposing parser objects.

Query policy declares filters, selectable fields, and quiet support. Filters
and selection reach the application query and repository port before the page
limit. Quiet output is a distinct machine mode: exactly one explicitly
selected value per undecorated line, with no envelope. Quiet plus `--format`,
quiet without one field, duplicate fields, and unknown fields are syntax
errors before execution. Continuations are opaque and bound to normalized
filter and field state. Quiet-selectable domain and catalog values are
single-line by construction, so one logical value cannot corrupt physical
line framing.

Mutation retry policy is a closed choice: unconditional, conditional, or
unsafe. `add --idempotency-key KEY` is conditionally idempotent. The
application-owned repository port atomically stores the normalized request
fingerprint with the created item. Same key and request replays the original
result without another item and a completed first attempt emits no second
event; the same key with different input
returns `idempotency_conflict`. Without a key, create remains compatible,
explicitly unsafe, and returns a distinct operation identifier. Persistence
stores only a digest of the secret key. This atomic boundary covers the domain
item and replay record. Event publication remains an explicit post-commit
port call; this example does not claim durable delivery or add an outbox.

Safety policy is a closed non-destructive/destructive variant. A destructive
declaration requires a preview flag, confirmation-bypass flag, and structured
plan fields. When a real destructive command is introduced, its independent
process case must supply categorized domain, persistence, event, audit, and
destination probes. Each category explicitly chooses CLI readback, workspace
artifact, or not applicable and states whether confirmed execution should
change it. Every applicable probe is unchanged by preview and unconfirmed
execution, then matches its declared confirmed-change expectation.
Closed-stdin execution without bypass fails closed and names the required
flag. Current commands are non-destructive and do not gain meaningless dry-run
controls.

Expected command failures are closed outcome declarations containing code,
coarse exit class, retryability, allowlisted detail keys, and a recovery hint.
Runtime translation selects those declarations. Shared syntax and unexpected
outcomes remain protocol-wide. Structured details may include safe rejected
values. Detail sources are a closed constant/computed/argument variant, runtime
failure construction requires matching provenance, and argument-source
declarations that reference sensitive arguments are rejected by command-schema
construction.

The flat `add`, `list`, and `capabilities` names remain. Revisit noun-verb
hierarchy only after a second resource group creates real discovery pressure.
Revisit CLI versus MCP only for stateful sessions, API-only access, or large
dynamic discovery; do not duplicate the schema speculatively.

## Alternatives considered

- **Make inline JSON the primary input.** Rejected without comparative
  evidence: shell quoting expands the failure surface and removes constrained
  option discovery.
- **Treat retry safety and dry-run as booleans.** Rejected: booleans hide
  preconditions and cannot require the controls or effects that make the claim
  true.
- **Render quiet output after fetching full objects.** Rejected: this would
  advertise composability while retaining unnecessary data access and could
  paginate before filtering.
- **Add a destructive sample command or MCP server for coverage.** Rejected:
  both are speculative product surface. Closed constructors make the contract
  mandatory when a real need appears.

## Consequences

### Positive

- Agents can discover valid input, stdin, retry, safety, query, and recovery
  behavior before execution.
- Same-request retries converge atomically across memory and SQLite adapters.
- Shell pipelines can consume selected line output without scraping JSON or
  human decoration.
- Independent process and port cases reject metadata that lacks behavior.

### Negative / cost accepted

- The example carries more catalog vocabulary, outcome declarations,
  idempotency storage, and process cases.
- A new command must specify more facts up front and provide independent cases
  for every declared feature and expected outcome.
- Durable event delivery remains outside the sample idempotency transaction;
  an application that needs recovery after publisher failure must add an
  application-owned outbox and its own delivery contract.

### Risks and mitigations

- *Idempotency keys leak:* sensitivity is cataloged, errors allowlist detail
  fields, detail sources cannot reference sensitive arguments, and adapters
  persist only SHA-256 digests.
- *Continuation tokens are treated as data:* tokens are opaque, validated,
  and rejected when selection state differs.
- *Help tests become brittle:* tests normalize whitespace and assert semantic
  type/default/choice facts, never exact wrapping or option order.
- *Closed variants overclaim future destructive behavior:* no destructive
  command exists; the process obligations activate only when one is cataloged.

## Validation

The generated `just check` gate runs exact command and outcome completeness,
including shared protocol outcomes; detached closed/open-stdin cases; help and
capability discovery; exact input, filter, field, and quiet declaration cases;
filter-before-pagination; continuation compatibility; exact quiet output;
invalid format combinations; concurrent conditional and unsafe replay;
conflict redaction; shared repository idempotency/filter contracts; and the
ARCH025 fitness function. Pack acceptance remains `just validate`.

## Migration and rollback

Existing command names, unkeyed `add`, JSON defaults, human format, schema
version, and exit values remain valid. SQLite creates the idempotency table
lazily with the existing item table. Rollback may leave that unused table; it
does not affect the original item schema. Remove the new catalog fields,
application port behavior, tests, ARCH025, and this ADR together only if the
agent-native extension is deliberately abandoned.

## Removal / supersession criteria

Supersede this ADR for an input-path removal, protocol-major change, new
command grammar, or protocol-server adoption. Preserve this record and attach
the comparative evidence or concrete product forces to the successor.
