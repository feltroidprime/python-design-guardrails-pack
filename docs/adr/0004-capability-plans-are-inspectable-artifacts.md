# ADR-0004: A capability was created through an inspectable plan

- Status: superseded
- Date: 2026-08-05
- Owners: repository maintainers
- Revisit trigger: none. This record is closed, and ADR-0001 with ADR-0008
  carry what replaced it.

## Context and forces

This record was written when a control plane inside every project created a
Product Capability in two steps. The first step wrote a plan document, and the
second step applied that document. Both steps are gone with the control plane.
The record is restored here because a decision is superseded, never deleted,
and because the documentation guard reads the ADR numbers as one contiguous
sequence.

## Decision

The original decision made every write of a new capability explicit and
reviewable before it happened. A plan named each path the tool would write, and
a second command applied an already inspected plan. A repeated apply reported
that the work was already done.

That decision is dead. A capability is now one directory that the owner writes
directly under the package, plus one import line in `composition.py`. Nothing
plans it, nothing applies it, and no record outside the code states that it
exists. Import presence in the composition root is the whole record.

## Alternatives considered

Recorded in the original: a direct write from the arguments of one command, and
a shipped default product module. The one-tree refactor of 2026-08-05 chose the
first, and it removed the tool that would have performed it.

## Consequences

### Positive

- A capability costs one directory, so no control surface has to guess product
  semantics.

### Negative / cost accepted

- No tool now reviews the writes of a new capability. Git does, at the same
  cost the owner already pays for every other change.

### Risks and mitigations

- *A reader treats this record as live policy:* the status above is
  `superseded`, and ADR-0001 states the live rule.

## Validation

The six `import-linter` contracts of `pack/configs/importlinter.ini` check the
layout of every capability directory the tree holds.

## Migration and rollback

Complete. No plan store remains to migrate.

## Removal / supersession criteria

This record is already superseded. It stays on disk so that the decision
history has no gap.
