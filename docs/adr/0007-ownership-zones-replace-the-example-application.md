# ADR-0007: Four ownership classes made the baseline product-empty

- Status: superseded
- Date: 2026-08-05
- Owners: repository maintainers
- Revisit trigger: none. ADR-0008 replaces this decision.

## Context and forces

The pack had to change its own infrastructure without overwriting a product.
Before the first Product Capability existed, a fresh tree still needed an
unambiguous answer to one question: which files does the pack own?

## Decision

The original decision classified every path into one of four classes, and a
policy file listed about forty roots to do it. One class held the shared
infrastructure, one held the product, one held derived indexes, and one held
the records that produced those indexes. Three hand-written validators guarded
the boundary.

ADR-0008 replaces all of it with two surfaces and one predicate. Two of the
four classes described artifacts that no longer exist, and a list of roots
cannot answer for a path that no one has written yet.

## Alternatives considered

Recorded in the original: treat every shipped file as infrastructure, which
would overwrite product work; and create an empty placeholder product
directory, which would imply semantics before the owner chose them. ADR-0001
still holds the second rejection.

## Consequences

### Positive

- Ownership was mechanical before any product existed.

### Negative / cost accepted

- The list of roots was long, and every new path needed an entry in it.

### Risks and mitigations

- *A reader treats this record as live policy:* the status above is
  `superseded`, and ADR-0008 states the live rule.

## Validation

Retired with the classifier it validated.

## Migration and rollback

Complete. ADR-0008 records the shape that replaced this one.

## Removal / supersession criteria

This record is already superseded. It stays on disk so that the decision
history has no gap.
