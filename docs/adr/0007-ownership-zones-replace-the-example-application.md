# ADR-0007: Ownership zones make N0 an empty product baseline

- Status: accepted
- Date: 2026-07-30
- Owners: repository maintainers
- Revisit trigger: a new ownership class or a capability cannot be classified
  by the declared roots

## Context and forces

The template must evolve its foundation without overwriting a user's product
work. A generated baseline also needs an unambiguous answer to which files are
template-owned before the first product capability exists.

## Decision

`architecture.toml` classifies every path as FOUNDATION, PRODUCT, DERIVED, or
DECLARATION. N0 contains FOUNDATION, DERIVED, and DECLARATION paths; PRODUCT
roots may be absent. Repository control is a FOUNDATION capability and uses the
same structure validator as a future product capability.

The package `_foundation` namespace names template-maintained code. Derived
indexes are empty projections of declarations. Product paths become user-owned
only when repository control materializes a declared capability.

## Alternatives considered

- **Treat every generated file as foundation.** Rejected: scaffold updates
  could overwrite user product work.
- **Create an empty placeholder product directory.** Rejected: its presence
  would imply product semantics and ownership before the user chooses them.

## Consequences

### Positive

- Ownership is mechanical before any product exists.
- The generator can prove that it does not ship into PRODUCT roots.

### Negative / cost accepted

- A fresh repository demonstrates control-plane behavior rather than a domain
  workflow.

### Risks and mitigations

- *A path drifts between zones:* ownership and architecture guards reject
  overlap and unclassified paths.

## Validation

The pack's ownership-zone regression check renders N0 and checks absent PRODUCT
roots, unchanged quality limits, and the single repository-control capability root.
`uv run python -m scripts.capability_validator --root
repoctl/modules/repository_generation` validates that root directly.

## Migration and rollback

Future foundation changes update FOUNDATION or DERIVED paths only. Product
changes require the user's declared capability and must preserve existing bytes.

## Removal / supersession criteria

Supersede this decision if the repository introduces a new ownership zone with
an equally explicit classifier and migration contract.
