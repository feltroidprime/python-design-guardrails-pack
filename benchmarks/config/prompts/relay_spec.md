# Build `relay`, an offline event-sourced job-queue command-line application

Deliver a production-quality Python 3.14 CLI called `relay` in the current
repository. Another team will maintain it after you, and a scripted evaluation
will run the exact commands below, so respect the contract precisely.

## Domain and time

A **job** has a positive integer id, a non-empty title, a Unicode-safe optional
note, an optional deadline, and one of four states. The state machine is:

```text
queued --start--> running --done--> done
                         \--fail--> failed --retry--> queued
```

`done` is terminal. `retry` is valid only for `failed`; `start` only for
`queued`; and `done`/`fail` only for `running`.

Every command requires global options `--log PATH --now DATETIME` immediately
after `relay`. `DATETIME` and deadlines use the exact UTC ISO-8601 form
`YYYY-MM-DDTHH:MM:SSZ`. Parse `--now` even for commands that do not otherwise
need time. Never read the wall clock for observable behavior.

## Event-sourced persistence

`PATH` is an append-only UTF-8 JSONL event log, created on the first successful
mutation. Current state must be derived by replaying it; there is no second
database or mutable snapshot. Each successful mutation appends exactly one
compact JSON object plus `\n` with keys `seq`, `at`, `type`, `job_id`, and
`data`. `seq` starts at 1 and increases globally. Event types are `enqueued`,
`started`, `completed`, `failed`, `retried`, and `imported`. Transition events
have empty `data`; `enqueued` carries `title`, `note`, and `deadline`; an
`imported` event carries all exported job fields except `id`. Validation
failures, reads, and skipped imports append nothing.

Ids assigned by `enqueue` are one greater than the largest id ever present,
starting at 1. Imported ids participate in that rule.

## Exit codes and errors

- `0`: success.
- `2`: invalid input, malformed log/import data, or import id collision with
  different job data.
- `3`: unknown job id.
- `4`: illegal state transition.

Every nonzero result prints a clear message on stderr and no success output.

## Command contract (exact)

Fields shown separated by `TAB` are one literal tab character. Successful
transition commands print nothing.

1. `relay --log PATH --now DATETIME enqueue --title TEXT [--note TEXT]
   [--deadline DATETIME]` appends `enqueued` and prints exactly `id=<integer>`.
   The omitted note is the empty string and an omitted deadline is null.
2. `start --id N`, `done --id N`, `fail --id N`, and `retry --id N` perform
   the transitions above. Unknown ids and illegal transitions use exits 3 and
   4 respectively.
3. `list [--state STATE] [--overdue]` prints matching jobs by increasing id:
   `<id>TAB<state>TAB<deadline-or->TAB<title-json>TAB<note-json>`. The title
   and note are JSON string literals emitted with Unicode characters intact.
   `--overdue` means deadline is strictly earlier than `--now` and state is
   `queued` or `running`; terminal jobs are never overdue. Filters combine.
   No matches print nothing.
4. `history --id N` prints that job's events by increasing global sequence:
   `<seq>TAB<at>TAB<event-type>TAB<resulting-state>`. Unknown id exits 3.
5. `stats` prints exactly one line in this fixed order:
   `queued=N running=N done=N failed=N overdue=N`. Overdue uses `--now` and
   the same definition as `list --overdue`.
6. `export --format json|csv --output FILE` writes current jobs by increasing
   id, replaces `FILE`, and prints `exported=N`. JSON is one compact UTF-8
   object `{"version":1,"jobs":[...]}` plus `\n`. Each job object has keys in
   this order: `id,title,note,deadline,state,created_at,updated_at`. CSV uses
   exactly that header order, UTF-8, RFC 4180 quoting, and `\n` line endings;
   null deadlines are empty fields. `created_at` is the enqueue/imported
   snapshot creation time; `updated_at` is the most recent event time.
7. `import --format json|csv --input FILE` accepts exactly the export schemas.
   A new id appends one `imported` event whose `at` is `--now` while preserving
   every exported job field in `data`. A record whose id and all exported job
   fields equal existing state is skipped. A differing existing id is invalid.
   Validate the complete input before appending anything, handle rows in a
   single linear pass (never replay the growing log per row), and print
   `imported=N skipped=M`. Re-importing an unchanged export is therefore a
   byte-for-byte no-op on the event log.

## Engineering requirements

- Python 3.14, project managed with `uv` (`pyproject.toml`); expose a console
  script named `relay` so `uv run relay ...` works from the repository root.
- Imports must remain linear for files containing thousands of jobs.
- An automated test suite runnable with `uv run pytest` must pass.
- Leave the repository in the state you would hand to the next maintainer.
