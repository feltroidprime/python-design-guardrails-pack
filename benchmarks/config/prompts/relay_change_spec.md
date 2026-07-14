# Change request: job priorities and scheduled jobs

Extend the existing event-sourced `relay` application in this repository.
Preserve the append-only replay model, injected `--now`, state machine, import
idempotence, and exits 0/2/3/4. Apply the change to the existing code with
tests; do not replace the application.

## New job fields and enqueue flags

Every job now has a priority `high`, `normal`, or `low` and an optional
`scheduled_at` timestamp. Add these optional enqueue flags:

`enqueue ... [--priority high|normal|low] [--scheduled-at DATETIME]`

Priority defaults to `normal`; omitted scheduling means immediately eligible.
Timestamps use the existing canonical UTC format. Invalid priority or time
prints a clear stderr message, exits 2, and appends nothing.

For backward compatibility, an enqueue with both new flags omitted keeps the
legacy three-key event data (`title,note,deadline`). If either new flag is
present, its `enqueued` data has keys in this exact order:
`title,note,deadline,priority,scheduled_at`. Replay accepts both forms, treating
legacy events as normal and unscheduled. Imported events follow the export
schema described below.

## Readiness, ordering, and overdue behavior

A job is **scheduled** when `scheduled_at` is strictly later than `--now`.
Scheduled jobs remain in state `queued`, but `start --id N` before that instant
is an illegal transition: stderr, exit 4, no event. At exactly `scheduled_at`
the job is eligible.

`list` continues to accept `--state` and `--overdue` and gains `--all`.
Without `--all`, future scheduled jobs are omitted. `--all` includes them.
Filters combine. Results are ordered by priority (`high`, then `normal`, then
`low`), then increasing id. When the log contains any extended job, each line
uses this exact tab-separated format:

`<id>TAB<state>TAB<priority>TAB<scheduled-at-or->TAB<deadline-or->TAB<title-json>TAB<note-json>`

A log containing only legacy jobs retains the original five-field list format.
An overdue job must be queued or running, already eligible at `--now`, and have
a deadline strictly earlier than `--now`. A future scheduled job is never
overdue, even when its deadline is earlier than `--now`.

For logs containing any extended job, `stats` prints exactly:
`queued=N running=N done=N failed=N scheduled=N overdue=N`. `scheduled` counts
future scheduled jobs regardless of deadline. Legacy-only logs retain the old
stats line.

## Export and import

When any current job is extended, JSON job objects and the CSV header use this
exact field order:
`id,title,note,deadline,priority,scheduled_at,state,created_at,updated_at`.
Legacy-only logs retain the original export schema. Import accepts either
complete schema but never a mixture within one file. The existing validation,
collision, streaming, atomicity, and byte-identical re-import guarantees still
apply. Export/import round-trips priority and scheduling exactly.

History output and transition-event data remain unchanged. `start`, `done`,
`fail`, and `retry` retain all existing state rules and success output.

## Engineering requirements

Keep Python 3.14 and the existing `uv` project and `relay` console script.
Replay and large imports remain linear. Add focused tests runnable by
`uv run pytest`, and leave the repository ready for another maintainer.
