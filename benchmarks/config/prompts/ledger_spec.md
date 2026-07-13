# Build `ledger`, a personal expense-ledger command-line application

Deliver a production-quality Python 3.14 CLI called `ledger` in the current
repository. Another team will maintain it after you, and a scripted evaluation
will run the exact commands below, so respect the contract precisely.

## Domain

An **expense** has: an amount in euros, strictly positive, with at most two
decimals; a **category** (non-empty lowercase slug such as `food`); an ISO
date `YYYY-MM-DD`; and an optional free-text note. A **monthly budget** sets a
positive limit for one category in one month (`YYYY-MM`). Budgets are
upserted: setting the same category and month again replaces the limit.

## Persistence

Data persists between invocations in a SQLite database file. Every command
takes a global `--db PATH` option immediately after `ledger`; the file is
created on first use.

## Command contract (exact)

All output formats below are contracts. Fields on one line are separated by
whitespace. Amounts always print with exactly two decimals.

1. `ledger --db PATH add --amount 12.50 --category food --date 2026-01-15 [--note TEXT]`
   records an expense and prints exactly one line `id=<integer>` on stdout;
   exit code 0. Ids are integers, unique per database.
2. Invalid input — amount that is zero, negative, or not a number; malformed
   or impossible date; empty category; malformed month — prints a clear
   message on stderr, exits with code 2, and stores nothing.
3. `ledger --db PATH list --month 2026-01` prints one line per expense of that
   month, oldest first: `<id>  <date>  <amount>  <category>  <note>` (empty
   note prints as nothing). A month with no expenses prints nothing. Exit 0.
4. `ledger --db PATH remove --id N` deletes the expense. Unknown id: message
   on stderr, exit code 3. Success: exit 0.
5. `ledger --db PATH budget set --category food --month 2026-01 --limit 100.00`
   upserts the budget; exit 0.
6. `ledger --db PATH budget status --month 2026-01` prints one line per
   budgeted category of that month:
   `<category>  spent=<S> limit=<L> remaining=<R>` where `R = L - S` and may
   be negative; all three print with two decimals. When `S > L` the line ends
   with ` OVER`. Exit 0.
7. `ledger --db PATH report --month 2026-01` prints one line per category with
   spending that month, highest total first, as `<category>  <total>`, then a
   final line `total  <sum>`. Exit 0.

## Engineering requirements

- Python 3.14, project managed with `uv` (`pyproject.toml`); expose the CLI as
  a console script named `ledger` so `uv run ledger …` works from the
  repository root.
- An automated test suite runnable with `uv run pytest` must pass.
- Leave the repository in the state you would hand to the next maintainer.
