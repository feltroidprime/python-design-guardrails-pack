# ADR-0003: Agent-session observability is an explicit project adapter

- Status: accepted
- Date: 2026-07-15
- Owners: repository maintainers
- Revisit trigger: Codex or Claude Code exposes a stable project-scoped native
  Langfuse integration, or retained transcripts fail the repository's privacy
  requirements

## Context and forces

Recurring agent friction is difficult to improve from final answers alone. A
failure such as `E501` can originate in a prompt, workflow order, formatter
limit, generated example, or quality gate, and those causes need different
changes. Humans need a replay in Langfuse; agents need the same evidence in a
machine-readable corpus. The evidence includes prompts, code, commands, tool
results, and skill content, so collection must remain a deliberate local
choice rather than an invisible default.

The official Codex and Claude Code integrations are hook-based plugins. Their
normal 20,000-character field ceiling conflicts with full-session diagnosis.
Codex's plugin manager also owns user-global mutable state, which a generated
repository must not replace.

## Decision

The repository ships one optional operator adapter under `scripts/` and one
authoritative workflow guide at `docs/agent-observability.md`.

- Installation requires project-scoped Langfuse credentials and both supported
  agents by default; a contributor may explicitly select one agent. Sequential
  installs enforce one base URL/public-key identity and synchronize secret-key
  rotations across every managed agent.
- Both official sources are checked out inside the ignored local observability
  directory at reviewed Git commits, and full working-tree cleanliness is
  checked before reuse or execution. Claude Code installs its plugin at local
  scope and the installed cache inventory/content must match every tracked
  source file. Codex uses a trusted project hook that changes to the repository
  root before invoking the pinned plugin, so config resolution is independent
  of the directory from which the session starts and no user-global Codex
  plugin state changes.
- Secrets, hook configuration, transcripts, and analysis corpora are ignored
  and written mode `0600`. Disable removes project hooks and credentials while
  preserving unrelated local settings. The adapter refuses unmanaged local
  Claude Langfuse plugin/settings, reuses a globally listed marketplace only at
  the clean reviewed revision without claiming ownership, and records its own
  ownership before external mutation, making partial installation failures
  cleanable.
- The capture ceiling is raised to 2,147,483,647 characters per field and
  Claude skill instruction content is enabled. Deployment-level payload and
  retention limits remain external constraints.
- Recent discovery and analysis page through every trace in a time window, retain only
  traces whose recorded root or working directory belongs to this repository,
  and summarizes recurring diagnostic codes by occurrence, trace, and distinct
  session. A single session can also be exported for causal drill-down.

The scripts are operator tooling, not application architecture. Ruff `S606`,
`S603`, and `S310` are excluded only for the three external-boundary modules
recorded in the exception ledger. Process calls use resolved executables and
shell-free argv. Langfuse URLs must be absolute HTTP(S) URLs.

## Alternatives considered

- **User-global Codex plugin installation.** Rejected: repositories would race
  to own one mutable plugin revision and could affect unrelated work.
- **Final-answer or quality-gate logs only.** Rejected: they omit the causal
  prompt/tool/retry chain needed to distinguish recurring harness failures.
- **Automatic tracing in every clone.** Rejected: consent, credentials,
  retention, and data residency differ by contributor and repository.
- **One-session export without aggregation.** Rejected: it supports anecdotes,
  not recurrence detection across agents and sessions.

## Consequences

### Positive

- Humans and agents can inspect the same evidence, and repeated diagnostic
  codes become countable hypotheses for template or harness changes.
- Plugin code and credentials stay project-scoped and revision-verifiable.
- Observability failure remains fail-open and never blocks the coding session.

### Negative / cost accepted

- Setup needs Git, network access, agent hook trust, and a Langfuse project.
- Full fields can create large or expensive traces; infrastructure may reject
  payloads before the local ceiling is reached.
- Diagnostic-code aggregation is intentionally narrow. Broader semantic pain
  analysis still belongs to an agent reading the exported corpus.

## Validation

Pack tests use fake agent/Git CLIs and a local HTTP server to prove pinning,
project scope, preservation of unrelated hooks/settings and a reused global
marketplace, secret handling, dirty-checkout rejection and repair, complete
trace export, repository-filtered multi-session paging, and recurring `E501`
detection across distinct sessions. The generated repository quality gate
checks formatting, strict types, architecture, documentation, and the scoped
Ruff exceptions.

## Migration and rollback

Existing repositories adopt the operator and guide through Copier update, then
run the explicit install command. Rollback runs the disable command and removes
this ADR, operator scripts, recipes, ignored paths, and exception-ledger entry.

## Removal / supersession criteria

Supersede this ADR when both agents provide a stable project-scoped integration
that preserves full transcripts, revision identity, fail-open behavior,
private credentials, and machine-readable multi-session export without these
operator adapters.
