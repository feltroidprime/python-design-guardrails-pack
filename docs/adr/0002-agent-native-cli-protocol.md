# ADR-0002: Every command answers with one machine envelope

- Status: superseded
- Date: 2026-08-05
- Owners: repository maintainers
- Revisit trigger: none. This record is closed, and ADR-0006 plus the router
  seam carry what survives of it.

## Context and forces

This record was written when a hand-maintained command catalog declared each
command, its inputs, its outcomes and its retry class. The catalog is gone.
The record is restored here because a decision is superseded, never deleted,
and because the documentation guard reads the ADR numbers as one contiguous
sequence.

## Decision

The original decision had two halves.

1. **The envelope.** Every command writes one JSON document with a fixed shape,
   a stable outcome code and a fixed exit code. A caller never reads a
   traceback, and a failure is data.
2. **The catalog.** A separate document listed every command, and derived code
   registered each one.

Half 1 survives, unchanged in substance. `_foundation/cli_protocol.py` writes
the envelope, `_foundation/cli_outcomes.py` holds the outcome codes and the
fixed exit codes, and `_foundation/router.py` maps a raised standard-library
exception onto them. A capability never selects an exit code.

Half 2 is dead. The router derives every group, subcommand, option and help
string from the signatures of the public functions of each `api.py`, and the
composed `CAPABILITIES` tuple is the only record of which capabilities exist.

## Alternatives considered

Recorded in the original: a bare exit status, and a per-command output shape.
Both were rejected because a caller then parses prose.

## Consequences

### Positive

- The envelope contract stayed stable while its declaration machinery died.

### Negative / cost accepted

- The original text named files that no longer exist, so this record replaces
  it rather than preserving it word for word.

### Risks and mitigations

- *A reader treats this record as live policy:* the status above is
  `superseded`, and ADR-0006 with `pack/docs/architecture/README.md` states the
  live seams.

## Validation

`pack/tests/test_router.py` covers the exception table, the envelope and the
exit codes.

## Migration and rollback

Complete. No catalog remains to migrate.

## Removal / supersession criteria

This record is already superseded. It stays on disk so that the decision
history has no gap.
