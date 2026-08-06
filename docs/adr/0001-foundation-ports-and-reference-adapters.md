# ADR-0001: A new project ships no product exemplar

- Status: accepted
- Date: 2026-08-05
- Owners: repository maintainers
- Revisit trigger: two Product Capabilities need the same foundation boundary
  that `_foundation/` does not already give them

## Context and forces

A new repository must be useful before it has a business domain. A sample
application makes its names, its ports and its command surface look like
obligations, and only the owner of the repository can choose those semantics.

## Decision

A new project ships the architecture policy, the tool policy, the proof system,
the gate, and the `_foundation` boundary of its package. It ships no Product
Capability and no product command. `composition.py` exports an empty
`CAPABILITIES` tuple, so the command line lists nothing until the owner
composes the first capability.

The first Product Capability is one directory that the owner adds directly
under the package, plus one import line in `composition.py`. Its domain, its
ports, its adapters and its public functions are the owner's decisions.

## Alternatives considered

- **A sample domain with reusable infrastructure.** Rejected: the sample
  becomes accidental product policy, and it widens every later migration.
- **An empty package with no shared boundary.** Rejected: the project must
  still prove that its ownership, proof and command mechanisms work.

## Consequences

### Positive

- The starting tree holds structure and policy only.
- Product semantics begin where the owner puts them.

### Negative / cost accepted

- A new project demonstrates no business workflow.

### Risks and mitigations

- *A later capability rebuilds generic plumbing:* widen `_foundation/` only
  after two capabilities supply the force, and record it in a new ADR.

## Validation

`pack/tests/test_router.py` covers the command surface that a composed
capability receives, and `pack/scripts/cli_surface.py` checks every `api.py`
against `CLI001` to `CLI004`. The `import-contracts` hook reports a project
with no capability as a fact rather than as a failure.

## Migration and rollback

Nothing to migrate: a fresh project starts in this state. To ship an exemplar
again needs a new ADR and a new ownership rule.

## Removal / supersession criteria

Supersede this decision only when repeated and measured demand for a shared
product boundary exists.
