# Documentation map

The single entry point to this repository's documentation. Find the row you
need; every document is one link away. The gate's `docs guard` check
(`pack/scripts/docs_guard.py`) keeps this map and the documents it registers
true.

## Rules

1. **One owner per fact.** Every documented fact lives in exactly one
   authoritative file — its row below. Other documents link to that file and
   never paraphrase it.
2. **Freshness ladder: derived > checked > dated.** Prefer documentation
   generated from the code. Prose whose file and
   directory references the gate verifies is *checked*: cite real repository
   paths, and renames fail the gate until the prose moves too. Prose no gate
   can verify — context, decisions, trade-offs — is *dated*: it carries a
   status, an owner, and a revisit trigger (the ADR front matter).
3. **Admission.** A new documentation file claims a row in the registry below
   in the same commit; the gate fails on unregistered files. A kind of
   knowledge with no fitting row requires an ADR before the file exists.

## Registry

| Document | Read it when | Freshness |
|---|---|---|
| [README.md](../README.md) | bootstrapping the project or looking up daily commands | checked |
| [AGENTS.md](../AGENTS.md) | before changing any code: the repository operating contract | checked |
| [CLAUDE.md](../CLAUDE.md) | never on its own: it imports [AGENTS.md](../AGENTS.md), which Claude Code does not read natively, so one contract governs every agent | checked |
| docs/README.md | deciding where a piece of knowledge belongs (this file) | checked |
| [docs/adr/](adr/) | understanding or recording a decision — one file per decision, numbered, never rewritten (start from [0000-template.md](adr/0000-template.md)) | dated |
| [pack/docs/architecture/README.md](../pack/docs/architecture/README.md) | needing the dependency direction, the stable seams, or the list of fitness functions | checked |
| [pack/docs/architecture/PROVABILITY.md](../pack/docs/architecture/PROVABILITY.md) | adding or changing an invariant, pure decision, retry protocol, or state machine | checked |
| [pack/docs/architecture/EXCEPTIONS.md](../pack/docs/architecture/EXCEPTIONS.md) | granting or auditing a suppression — the exception ledger | checked |
| [pack/docs/architecture/PATTERN_ADMISSION.md](../pack/docs/architecture/PATTERN_ADMISSION.md) | admitting a non-trivial pattern — the form to copy into an ADR | checked |
| [pack/docs/architecture/MIGRATION_CHECKLIST.md](../pack/docs/architecture/MIGRATION_CHECKLIST.md) | replacing or strangling an existing implementation safely | checked |
| [.github/PULL_REQUEST_TEMPLATE.md](../.github/PULL_REQUEST_TEMPLATE.md) | opening a pull request | checked |

In-code documentation is not listed here: each package's `__init__.py`
docstring states its public surface and ownership (ARCH015 in
[AGENTS.md](../AGENTS.md)), and module docstrings state the one non-obvious
constraint the code cannot show.
