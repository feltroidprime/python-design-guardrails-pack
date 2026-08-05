# ADR-0001: N0 ships no product exemplar

- Status: accepted
- Date: 2026-07-30
- Owners: repository maintainers
- Revisit trigger: a declared product capability needs a reusable foundation
  boundary that repository control does not already provide

## Context and forces

A generated repository must be useful without inventing a business domain.
A sample application makes its names, ports, and command surface look like
template obligations even though only the repository user can choose those
semantics.

## Decision

N0 ships the repository-control capability, architecture policy, proof system,
the package `_foundation` namespace, and empty derived indexes. It ships no
product module or product command. The small package-level CLI declarations
remain only because repository control imports them; they are compatibility
protocols, not an application exemplar.

The first product capability is introduced through repository control and is
immediately PRODUCT-owned. Its domain, ports, adapters, and lifecycle are
chosen by the user rather than copied from a template placeholder.

## Alternatives considered

- **A sample domain with reusable infrastructure.** Rejected: the sample
  becomes accidental product policy and widens every later migration.
- **An empty package with no control plane.** Rejected: N0 must still prove
  that its declaration, ownership, generation, and proof mechanisms work.

## Consequences

### Positive

- The generated baseline contains only template-maintained foundation and
  repository-control behavior.
- Product semantics begin at an explicit declaration boundary.

### Negative / cost accepted

- N0 demonstrates repository generation rather than a business workflow.

### Risks and mitigations

- *Future capabilities recreate generic plumbing:* introduce a shared
  foundation boundary only after a real capability supplies the force and an
  ADR records it.

## Validation

The pack's ownership-zone regression check proves that generated N0 contains no
PRODUCT root. `tests/foundation/test_cli_protocol.py` covers the retained compatibility
protocol, while `tests/repoctl/test_draft_capsule.py` validates the sole system
capability.

## Migration and rollback

The template migration deletes the placeholder surface before a user creates a
real capability. Restoring a shipped product exemplar would require a new ADR
and a new declared ownership contract.

## Removal / supersession criteria

Supersede this decision only when a real, repeated foundation requirement is
demonstrated by declared capabilities.
