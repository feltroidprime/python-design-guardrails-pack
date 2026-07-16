# Domain documentation

This repository uses a single-context documentation layout.

Before exploring a change, engineering skills read `CONTEXT.md` when it exists
and the relevant decisions under `docs/adr/`. Missing files are not an error:
domain-modeling workflows create them only when vocabulary or decisions need a
durable owner.

Use the vocabulary defined by `CONTEXT.md` in specs, tickets, tests, and design
documents. Surface any conflict with an accepted ADR explicitly instead of
silently overriding it.
