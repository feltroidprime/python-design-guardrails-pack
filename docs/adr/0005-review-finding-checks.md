# ADR-0005: Check recurring review findings

- Status: accepted
- Date: 2026-07-17
- Owners: repository maintainers
- Revisit trigger: a false positive, or three similar misses

## Context and forces

A review audit found rules that every reviewer repeated by hand and no tool
carried. A rule that only prose states is a rule that a tired reviewer drops.

## Decision

Five architecture codes carry those rules, and each one accepts an
`ARCH-EXCEPTION: ADR-NNNN` marker.

- ARCH026 rejects a mutable module container, except a list `__all__`.
- ARCH027 rejects two Enum classes with the same name.
- ARCH028 rejects a `str` parameter that names a path with no type token.
- ARCH029 rejects a CamelCase alias of a primitive type that code uses.
- ARCH030 rejects an override that no marker resolves.

ARCH027 makes no semantic inference. ARCH029 ignores an import. ARCH030 skips a
relative or module-alias import, a transitive ancestor, a structural `Protocol`,
a re-export, a dynamic base, and every ambiguous case. `JsonString` and
`JsonNumber` are allowed.

A sixth code once rejected a comment that scheduled manual upkeep. Ruff's `TD`
and `FIX` families replace it, so a maintained tool carries the rule instead of
pack code. Conflict C18 of #85 settles that, and the code and its edit-time
hook are both deleted.

## Alternatives considered

Prose repeats the audit and changes nothing. Semantic inference is noisy.

## Consequences

### Positive

A syntax finding leaves the review and enters the gate.

### Negative / cost accepted

Conservative resolution misses the broader cases.

### Risks and mitigations

Paired fixtures bound the drift of each heuristic.

## Validation

`pack/tests/test_review_discipline.py` holds a violating, a clean and a
suppressed fixture for each code, and the `architecture` hook of the gate runs
them all.

## Migration and rollback

Adopt the required form. To roll back, delete the five codes and this document
together.

## Removal / supersession criteria

Supersede with equivalent analyzer rules, or with evidence that the set must
grow.
