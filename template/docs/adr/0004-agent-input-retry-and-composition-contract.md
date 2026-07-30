# ADR-0004: Capability plans are explicit, inspectable control artifacts

- Status: accepted
- Date: 2026-07-30
- Owners: repository maintainers
- Revisit trigger: a capability lifecycle operation needs a different durable
  transaction boundary

## Context and forces

Repository control may create the first product capability, but it must not
guess product semantics or mutate a repository from an opaque command request.

## Decision

`repoctl capability plan` converts explicit capability intent into canonical,
inspectable operations in the plan store. `repoctl capability apply`
executes an already inspected plan through the repository port and replays a
completed transaction as `already_applied`.

Planning receives ownership roots and prior file digests in an explicit
snapshot. It plans creation only for absent PRODUCT seeds; applying the plan
writes them. Saved plans are not declaration state. Activation and retirement
update declarations without rewriting PRODUCT files.

## Alternatives considered

- **Apply directly from command arguments.** Rejected: users could not inspect
  the exact intended writes or retry a durable operation safely.
- **Ship a default product module.** Rejected: it would make repository control
  choose a domain on the user's behalf.

## Consequences

### Positive

- The first product capability begins from explicit user intent.
- Retries and lifecycle changes have inspectable, deterministic boundaries.

### Negative / cost accepted

- A control operation is two steps when a user needs to inspect its plan.

### Risks and mitigations

- *Plan state leaks into the snapshot:* plan artifacts are excluded from the
  planning digest and covered by repository-control evidence.

## Validation

`tests/repoctl/integration/test_cli_mutations.py` and
`tests/repoctl/unit/test_plan_models.py` cover planning and replay. The proof
catalogs under `proof/repoctl/` declare the corresponding deterministic and
non-destructive properties.

## Migration and rollback

Discard an un-applied plan artifact to abandon a proposed capability. Roll back
an applied change through a new explicit repository-control operation; never
delete PRODUCT files implicitly.

## Removal / supersession criteria

Supersede this ADR when a replacement transaction protocol preserves explicit
intent, inspectability, exact preconditions, and replay semantics.
