# Change request: recurring expenses and historical category renames

Extend the existing `ledger` application in this repository. Preserve every
existing command, output format, persistence guarantee, and exit code. Apply
the change as production code with tests; do not replace the application.

## Recurring expense rules

A recurring rule has a positive integer id, the same validated amount,
category, and optional note as an expense, a `start` date, and a positive
`interval-months`. Add these exact commands:

1. `ledger --db PATH recurring add --amount AMOUNT --category CATEGORY
   --start YYYY-MM-DD [--note TEXT] [--interval-months N]` stores a rule and
   prints exactly `recurring_id=<integer>`. `--interval-months` defaults to 1.
   Invalid values print a message on stderr, exit 2, and store nothing.
2. `ledger --db PATH recurring apply --through YYYY-MM-DD` materializes every
   occurrence whose date is between each rule's start and `--through`,
   inclusive, and prints exactly `created=N`. An occurrence is stored as a
   normal expense with the rule's current amount, category, and note. Applying
   the same or an earlier date again is idempotent and prints `created=0`.
3. Monthly recurrence keeps the start day when possible and otherwise uses the
   last valid day of that month: a rule starting `2026-01-31` produces
   `2026-02-28`, `2026-03-31`, and so on. Advance from the original start month,
   never from the previously clamped date.

Persist rules and materialized-occurrence identity in SQLite. Applying all due
rules is one transaction: validation or storage failure must not leave a
partial batch.

## Rename a category everywhere

Add `ledger --db PATH category rename --from OLD --to NEW`. Both values use the
existing category validation. On success, atomically rename the category in
all historical expenses, all monthly budgets, and all recurring rules, then
print exactly:

`expenses=E budgets=B recurring=R`

where each number is the count of rows changed. If `OLD` does not occur in any
of those three places, print a clear message on stderr, exit 3, and change
nothing. If moving budgets would collide with an existing `(NEW, month)`
budget, print a clear message on stderr, exit 2, and change nothing.

All existing reads observe the rename: `list`, `budget status`, and `report`
must show only `NEW`. Future materialized occurrences also use `NEW`. Existing
expense ids and recurring ids do not change. All other invalid input remains
exit 2; existing unknown expense ids remain exit 3.

## Engineering requirements

Keep Python 3.14 and the existing `uv` project and console script. Add focused
automated tests runnable by `uv run pytest`. Leave the repository ready for a
different maintainer to continue working in it.
