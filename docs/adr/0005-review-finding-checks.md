# ADR-0005: Check recurring review findings

- Status: accepted
- Date: 2026-07-17
- Owners: repository maintainers
- Revisit trigger: a false positive or three similar misses

## Context and forces

E0 found repeated unenforced rules:
/Users/felt/PycharmProjects/ai/base_repos/workflow-audit/.audit/analysis/E0-mechanical-gate-replay.md

## Decision

ARCH026 rejects mutable module containers except list `__all__`; ARCH027 exact
same-named Enums; ARCH028 untokenized `str` path use; ARCH029 used CamelCase
primitive aliases; ARCH030 unmarked resolved overrides; and ARCH031 reminder
comments that schedule manual upkeep instead of deriving the value or enforcing
the invariant with a test or gate check. All accept `ARCH-EXCEPTION: ADR-XXXX`.

ARCH027 avoids semantic inference; ARCH029 ignores imports; ARCH030 skips
relative/module-alias imports, transitive ancestors, structural Protocols,
re-exports, dynamic bases, and ambiguity. `JsonString`/`JsonNumber` are allowed.
ARCH031 matches a closed set of English phrases in comment tokens only; string
literals and docstrings are never inspected.

## Alternatives considered

Prose repeats E0; semantic inference is noisy.

## Consequences

### Positive

Syntax findings leave review.

### Negative / cost accepted

Conservative resolution misses broader cases.

### Risks and mitigations

Paired fixtures bound heuristic drift.

## Validation

Violating, clean, and suppression fixtures; generated `just check`; pack
`just validate`.

## Migration and rollback

Adopt the required form; roll back all six codes and docs together.

## Removal / supersession criteria

Supersede with equivalent analyzer rules or evidence for expansion.
