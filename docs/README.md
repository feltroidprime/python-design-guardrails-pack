# Documentation map

The single entry point to this repository's documentation. Find the row you
need. Every document is one link away. The `docs` hook of the gate
(`pack/scripts/docs_guard.py`) keeps this map and the documents it registers
true.

## Rules

1. **One owner per fact.** Every documented fact lives in exactly one
   authoritative file — its row below. Another document links to that file and
   never repeats it in other words.
2. **Freshness ladder: derived > checked > dated.** Prefer documentation that
   the code generates. Prose whose file and directory references the gate reads
   is *checked*. Cite real repository paths in that prose. A rename then fails
   the gate until the prose moves too. Prose that no gate can read — context,
   decisions, trade-offs — is *dated*: it carries a status, an owner and a
   revisit trigger in its front matter.
3. **Admission.** A new documentation file claims a row below in the same
   commit, and the gate fails on an unregistered file. A kind of knowledge that
   no row fits needs an ADR before the file exists.
4. **Scope.** The `docs` hook reads `*.md` files only. A file with another
   suffix, for example an `.mdx` file of `docs/vendored/`, needs no row here.

## Registry

| Document | Read it when | Freshness |
|---|---|---|
| [README.md](../README.md) | starting the project, or looking up a daily command | checked |
| [AGENTS.md](../AGENTS.md) | before changing any code: the one contract of this repository | checked |
| [CLAUDE.md](../CLAUDE.md) | never on its own: it imports [AGENTS.md](../AGENTS.md), which Claude Code does not read natively, so one contract governs every agent | checked |
| [CONTEXT.md](../CONTEXT.md) | before you name a thing: the vocabulary, and the words each concept retired | dated |
| [DESIGN_GUARDRAILS.md](../DESIGN_GUARDRAILS.md) | asking which check carries which design decision, and why a rule was loosened | checked |
| [CHANGELOG.md](../CHANGELOG.md) | asking what changed in a release, and what a project can adopt | dated |
| [VALIDATION.md](../VALIDATION.md) | asking what the last full run of the gate actually proved, and on what machine | dated |
| docs/README.md | deciding where a piece of knowledge belongs (this file) | checked |
| [docs/adr/](adr/) | understanding or recording a decision — one file per decision, numbered, superseded but never deleted (start from [0000-template.md](adr/0000-template.md)) | dated |
| [docs/agents/](agents/) | working through the issue tracker, the triage labels, or the domain documents | dated |
| [docs/vendored/](vendored/) | choosing a vendored library, or hardening it for production: a pinned, read-only third-party manual | dated |
| [pack/docs/architecture/README.md](../pack/docs/architecture/README.md) | needing the dependency direction, the stable seams, or the list of fitness functions | checked |
| [pack/docs/architecture/PROVABILITY.md](../pack/docs/architecture/PROVABILITY.md) | adding or changing a law, a pure decision, a retry protocol, or a state machine | checked |
| [pack/docs/architecture/EXCEPTIONS.md](../pack/docs/architecture/EXCEPTIONS.md) | granting or auditing a suppression — the exception ledger | checked |
| [pack/docs/architecture/PATTERN_ADMISSION.md](../pack/docs/architecture/PATTERN_ADMISSION.md) | admitting a non-trivial pattern — the form to copy into an ADR | checked |
| [pack/docs/architecture/MIGRATION_CHECKLIST.md](../pack/docs/architecture/MIGRATION_CHECKLIST.md) | replacing an existing implementation safely | checked |
| [.github/PULL_REQUEST_TEMPLATE.md](../.github/PULL_REQUEST_TEMPLATE.md) | opening a pull request | checked |

In-code documentation is not listed here: the `__init__.py` docstring of each
package states its public surface and its ownership. `ARCH015` of
[AGENTS.md](../AGENTS.md) states that rule, and
[pack/scripts/architecture_rules.py](../pack/scripts/architecture_rules.py)
enforces it. A module docstring states the one non-obvious constraint that the
code cannot show.

## Outside this map

`.agents/skills/` holds 43 skill directories, and `skills-lock.json` pins their
versions. `epics/` holds a `.gitkeep` marker and no other tracked file.
`pack/configs/prek.toml` excludes `.agents/` from the gate. No row above
governs these three paths, because they hold skill assets and an empty
directory marker rather than documentation.
