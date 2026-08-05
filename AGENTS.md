# AGENTS.md — the contract of this repository

This file is normative for every coding agent and every human who changes this
repository. There is one contract, and this is it. `CLAUDE.md` imports this
file, so one document governs every agent.

## What this repository is

A Python 3.14 project with an executable architecture and quality contract. The
structure, the tool policy and the gate are here from the first commit. The
product model is your decision.

The tree holds two kinds of file, and one predicate divides them.

> **Pack-owned** is the `pack/` directory at the repository root, plus
> `_`-prefixed names and `py.typed` inside `src/<package>/`.
> **User-owned** is everything else.

`pack/scripts/ownership.py` holds that predicate, and it is the only ownership
code in the tree. No file holds a list of ownership roots. ADR-0008 records the
decision.

An update of the pack replaces whole pack-owned files, and it writes no
user-owned file. So a change you make to a pack-owned file is a change to the
pack: git records the drift, and the next update refuses until a human reverts
it or passes `--force`.

Four user-owned files at the root are thin entry points into `pack/`:

| Entry point | It carries |
|---|---|
| `justfile` | one `import` of `pack/justfile`, which holds every recipe |
| `pyrightconfig.json` | one `extends` of `pack/configs/pyrightconfig.json` |
| `.python-version` | the 3.14 pin |
| `.github/workflows/quality.yml` | one call of `pack/ci/action.yml` |

An update reports a suggested change to each one and never writes it.

## The one gate

```bash
just check
```

That runs `prek run --all-files -c pack/configs/prek.toml`: twelve hooks, in
this order.

```
lockfile  format  lint  types  dependencies  architecture
docs  proof  symbolic  import-contracts  tests  manifest
```

CI runs the same command, so a local run and a CI run cannot disagree. The gate
never rewrites a file. `just fix` applies the deterministic repairs, and
`just manifest` records the pack-owned bytes after you edit a pack-owned file.

Every tool reads its policy from `pack/configs/`. That path is a stable ABI: a
release can change the content of a file there, and never its name or its
location. Do not add a second policy file beside it.

## Sources of truth

| Concern | Source of truth |
|---|---|
| Project identity | `pyproject.toml`, in two values: the project name and the package |
| Which capabilities exist | the `CAPABILITIES` tuple of `src/<package>/composition.py` |
| The command line | `_foundation/router.py`, which derives it from each `api.py` |
| Limits, conventions and domain purity | `pack/architecture.toml` |
| Import direction | the six contracts of `pack/configs/importlinter.ini` |
| Tool policy | `pack/configs/` |
| The gate | `pack/configs/prek.toml` |
| Laws and their evidence | `pack/proof/policy.toml` and each `proof.toml` |
| Ownership | `pack/scripts/ownership.py` |
| The record of pack-owned bytes | `pack/manifest.json` |
| Architecture rationale | `pack/docs/architecture/README.md` |
| Design-to-guardrail rationale | `DESIGN_GUARDRAILS.md` |
| Vocabulary | `CONTEXT.md` |

## Add a capability

A Product Capability is one directory directly under `src/<package>/`, plus one
import line in `src/<package>/composition.py`.

```
src/<package>/orders/
├── api.py                 the public functions, which become subcommands
├── domain/                pure rules, with no I/O
├── application/           the ordered steps
├── adapters/inbound/      the ways in
├── adapters/outbound/     the ways out
├── proof.toml             the laws this capability owns
└── tests/
```

Four rules hold, and the six `import-linter` contracts carry them.

1. One directory per capability, directly under the package, with that layer
   set. There is no container directory and no nesting.
2. Layers point inward: `api`, `domain`, `application`, `adapters`.
3. Reach a capability through its `api` module, never through its internals.
4. A capability imports neither a sibling capability nor pack code. If it needs
   a sibling, declare a `Protocol` port in its own domain layer, and let the
   composition root inject the sibling's `api` as the adapter.

Import the `api` module in `composition.py` and add it to `CAPABILITIES`. The
command line then carries one subcommand for each public function of `api.py`.
Nothing else records the capability. A directory that `composition.py` never
imports is not composed yet, and the gate reports that as a fact.

The router derives every group, option, help string, envelope, page and exit
code from stdlib-typed signatures. So four rules hold over every `api.py`:
`CLI001` rejects a reserved parameter name, `CLI002` a missing docstring,
`CLI003` an annotation outside the closed set the router can render, and
`CLI004` a `bool` parameter that does not default to `False`. A capability
never selects an exit code.

## Change protocol

1. **Fix the source, never a copy.** Each fact has one owner. Change that file,
   and let every other document link to it.
2. **Never weaken a guardrail in silence.** To loosen a ceiling, a lint rule, a
   type setting or an architecture rule, state the rationale in the change
   description, and update `DESIGN_GUARDRAILS.md` in the same change.
3. **Use the exception path instead of a wall.** A narrow suppression with an
   `ARCH-EXCEPTION: ADR-NNNN` marker is legal, and
   `pack/docs/architecture/EXCEPTIONS.md` is the ledger it must enter.
4. **Keep version pins coherent.** Some pins deliberately exist in more than
   one place. `pack/tests/test_pin_coherence.py` finds every occurrence by
   scanning the tracked tree, so move a pin, then fix the copies that the test
   reports. Register a new multi-location pin in that test in the same change.
5. **Record a decision before you build the pattern.** A non-trivial pattern
   needs an ADR under `docs/adr/`, and
   `pack/docs/architecture/PATTERN_ADMISSION.md` is the form to copy into it.
   ADR numbers are contiguous from 0000: supersede a record, never delete it.
6. **Add a law with its evidence.** A new law needs its catalog entry, its
   independent oracle, its `icontract` condition, its Hypothesis evidence and
   its symbolic target, in one change.

## Proof

`just prove` is the fast local loop: structural closure, bounded generators,
then the symbolic core. `just prove-one PROPERTY-ID` narrows it to one law.
`just prove-deep` widens the search for a release candidate.
`pack/docs/architecture/PROVABILITY.md` states what an oracle may do.

## Documentation synchronization

When behavior changes, update the documents that state it, in the same change:

- `README.md`: the daily commands and what the repository is;
- `docs/README.md`: the documentation map, which every new document must join;
- `DESIGN_GUARDRAILS.md`: when a guardrail is added, removed or materially
  changed;
- `pack/docs/architecture/`: when a seam, a fitness function or an exception
  changes;
- `CHANGELOG.md`: one entry per user-visible change, newest first;
- `VALIDATION.md`: replace the record when you re-run the gate after a material
  change. Date it, and state the environment honestly.

The `docs` hook checks every path a document claims, so a rename fails the gate
until the prose moves too.

## Completion reporting

A completion report must state:

- files changed, and why;
- tests added or updated;
- exact commands run, and their actual results;
- whether `just check` was run, and its outcome;
- remaining risks or portability notes.

Never claim a check you did not run. If the gate fails, report the failure word
for word rather than narrowing the claim.

## Agent skills

### Issue tracker

Specs and tickets live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the five standard triage labels, including
`ready-for-agent`. See `docs/agents/triage-labels.md`.

### Domain docs

The repository uses a single-context domain documentation layout. See
`docs/agents/domain.md`.

<!-- vendored-docs:begin -->
## Vendored documentation

Before writing code against these libraries, read the page named below instead of recalling the
API from memory. These trees are pinned and read-only; `vendor-docs check` fails on local edits.

| Read | When | Pin |
|---|---|---|
| `docs/vendored/arize_phoenix/phoenix/` | before choosing Phoenix capabilities for an AI application | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/get-started/` | before adding Phoenix to an application | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/tracing/` | before instrumenting application tracing or annotating spans | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/evaluation/` | before implementing Phoenix evaluators or server-side evaluations | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/datasets-and-experiments/` | before creating Phoenix datasets or experiment workflows | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/prompt-engineering/` | before storing, versioning, or testing prompts with Phoenix | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/integrations/` | before wiring Phoenix to a provider, framework, language, or coding agent | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/` | before choosing a local, notebook, container, or cloud Phoenix environment | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/self-hosting/` | before deploying or upgrading a self-hosted Phoenix instance | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/` | before hardening a Phoenix tracing pipeline or server for production | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/settings/` | before configuring Phoenix authentication, access control, providers, secrets, or sandboxes | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/cookbook/` | before adapting an end-to-end Phoenix workflow pattern | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/use-cases/` | before evaluating a RAG application with Phoenix | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/resources/frequently-asked-questions/` | before troubleshooting Phoenix setup or behavior | arize-phoenix-v18.0.0 |
<!-- vendored-docs:end -->
