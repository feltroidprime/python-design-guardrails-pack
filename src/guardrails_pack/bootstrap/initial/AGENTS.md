# AGENTS.md — the contract of this repository

This file is normative for every coding agent and every human who changes this
repository. There is one contract, and this is it. `CLAUDE.md` imports this
file, so one document governs every agent.

## What this repository is

A Python 3.14 project with an executable architecture and quality contract. The
structure, the tool policy and the gate are here from the first commit. The
product model is your decision.

A Root Pack projected this repository once, and this repository can create no
other. `CONTEXT.md` defines that term, alongside Terminal Project and
Pack-owned Surface: read it before you name a new thing.

The tree holds two kinds of file, and one predicate divides them.

> **Pack-owned** is the `pack/` directory at the repository root, plus
> `_`-prefixed names and `py.typed` inside `src/<package>/`.
> **User-owned** is everything else.

`pack/scripts/ownership.py` holds that predicate, and it is the only ownership
code in the tree. No file holds a list of ownership roots. ADR-0008 records the
decision. `pack/tests/test_gate_definition.py` proves that no pack-owned file
names this project, so pack-owned code stays replaceable.

An update of the pack replaces whole pack-owned files, and it writes no
user-owned file. So a change you make to a pack-owned file is a change to the
pack: git records the drift, and the next update refuses until a human reverts
it or passes `--force`. After you edit a pack-owned file, run
`just manifest`, or the `manifest` hook of the gate fails.

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

That runs `prek run --all-files -c pack/configs/prek.toml`: eleven upstream
file hooks, then twelve local hooks, in this order.

```
lockfile  format  lint  types  dependencies  architecture
docs  proof  symbolic  import-contracts  tests  manifest
```

CI runs the same command in the `quality` job of
`.github/workflows/quality.yml`, and that job is the whole of CI. So a local
run and CI cannot disagree.

The `tests` hook skips two pytest markers, `acceptance` and `session_e2e`. No
job of this repository runs them, so a test you mark with either one runs
nowhere until you add a job for it.

The twelve local hooks never rewrite a file. Three upstream hooks do repair a
file in place: `end-of-file-fixer`, `mixed-line-ending` and
`trailing-whitespace`. Each one fails its own run after it writes the repair.
When one of these three fails, run `just check` again, then commit the
repair. `just fix` applies the deterministic repairs, and `just manifest`
records the pack-owned bytes after you edit a pack-owned file.

Every tool reads its policy from `pack/configs/`. That path is a stable ABI: a
release can change the content of a file there, and never its name or its
location. Change the content of the existing file there instead of adding a
second one beside it.

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
├── adapters/inbound/      the ways in
├── adapters/outbound/     the ways out
├── application/           the ordered steps
├── domain/                pure rules, with no I/O
├── proof.toml             the laws this capability owns
└── tests/
```

Four rules hold, and the six `import-linter` contracts carry them.

1. One directory per capability, directly under the package, with that layer
   set. There is no container directory and no nesting. Each of the four
   layer directories exists and holds at least one module besides
   `__init__.py`. A declared layer that does not exist, or that holds only an
   empty `__init__.py`, breaks the contract.
2. Layers point inward, in this order: `api`, `adapters`, `application`,
   `domain`. `api` imports `adapters`, `adapters` imports `application`, and
   `application` imports `domain`. The `domain` layer imports no other layer.
3. Reach a capability through its `api` module, never through its internals.
4. A capability imports neither a sibling capability nor pack code. If it needs
   a sibling, declare a `Protocol` port in its own domain layer, and let the
   composition root inject the sibling's `api` as the adapter.

Before you write the first module of the domain layer, read the `[domain]`
table of `pack/architecture.toml`. Pass a clock, a random source or an I/O
result in as a parameter instead of reading it in the domain layer.

Every `__init__.py` states the package's public surface and its ownership
zone in its docstring, and `ARCH015` enforces that rule. Every module
docstring states the one non-obvious constraint the code cannot show.

Import the `api` module in `composition.py` and add it to `CAPABILITIES`. The
command line then carries one subcommand for each public function of `api.py`.
Nothing else records the capability. A directory that `composition.py` never
imports is not composed yet, and the gate reports that as a fact.

The router derives every group, option, help string, envelope, page and exit
code from stdlib-typed signatures. The router selects every exit code, and a
capability returns a value or raises. Four rules hold over every `api.py`,
and `pack/scripts/cli_surface.py` states the closed annotation set:

- `CLI001` bans a parameter named `continuation`, `debug`, `format` or
  `limit`. The router reserves those four names.
- `CLI002` requires a docstring on the module and on each public function.
- `CLI003` bans an annotation outside the closed stdlib set the router can
  render.
- `CLI004` requires a `bool` parameter to default to `False`.

## Change protocol

1. **Fix the source, never a copy.** Each fact has one owner. Change that file,
   and let every other document link to it.
2. **State the rationale before you loosen a guardrail.** To loosen a
   ceiling, a lint rule, a type setting or an architecture rule, state the
   rationale in the change description, and update `DESIGN_GUARDRAILS.md` in
   the same change.
3. **Use the exception path instead of a wall.** A narrow suppression with an
   `ARCH-EXCEPTION: ADR-NNNN` marker is legal for `ARCH016` through
   `ARCH030`, and `pack/docs/architecture/EXCEPTIONS.md` is the ledger it
   must enter. The marker does not suppress `ARCH000` through `ARCH015`,
   because those codes are structural. For one of those, change the code
   instead, or change `pack/architecture.toml` with a written rationale.
4. **Keep version pins coherent.** Some pins deliberately exist in more than
   one place. `pack/tests/test_pin_coherence.py` finds every occurrence by
   scanning the tracked tree, so move a pin, then fix the copies that the test
   reports. Register a new multi-location pin in that test in the same change.
5. **Record a decision before you build the pattern.** A non-trivial pattern
   needs an ADR under `docs/adr/`, and
   `pack/docs/architecture/PATTERN_ADMISSION.md` is the form to copy into it.
   ADR numbers are contiguous from 0000: supersede a record, never delete it.
6. **Replace a running implementation through the checklist.**
   `pack/docs/architecture/MIGRATION_CHECKLIST.md` states the two safe
   sequences. Copy the one you use into the change description, and name the
   deletion condition for the old path before you shift any traffic.
7. **Add a law with its evidence.** A new law needs its catalog entry, its
   independent oracle, its `icontract` condition, its Hypothesis evidence and
   its symbolic target, in one change.

## Proof

`just prove` is the fast local loop: structural closure, bounded generators,
then the symbolic core. `just prove-one PROPERTY-ID` narrows it to one law.
`just prove-deep` widens the search for a release candidate.

Before you add a law, change an oracle, or add a capability's first
property, read `pack/docs/architecture/PROVABILITY.md`. It states the
evidence sequence and the rules an oracle must obey.

## Documentation synchronization

When behavior changes, update the documents that state it, in the same change:

- `README.md`: the daily commands and what the repository is.
- `docs/README.md`: the documentation map, which every new document must join.
- `DESIGN_GUARDRAILS.md`: when a guardrail is added, removed or materially
  changed.
- `pack/docs/architecture/`: when a seam, a fitness function or an exception
  changes.
- `CHANGELOG.md`: one entry per user-visible change, newest first.
- `VALIDATION.md`: replace the record when you re-run the gate after a material
  change. Date it, and state the environment honestly. The file this repository
  starts with records no run, and it states the shape of one.

The `docs` hook checks every path a document claims, so a rename fails the gate
until the prose moves too.

## Completion reporting

A completion report must state:

- files changed, and why.
- tests added or updated.
- exact commands run, and their actual results.
- whether `just check` was run, and its outcome.
- remaining risks or portability notes.

Report every command you ran, with its exit code and its last output line,
copied from the terminal. A command absent from that list did not run. If the
gate fails, report the failure word for word rather than narrowing the claim.

## Agent skills

### Issue tracker

Specs and tickets live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the five standard triage labels, including
`ready-for-agent`. See `docs/agents/triage-labels.md`.

### Domain docs

The repository uses a single-context domain documentation layout. See
`docs/agents/domain.md`.

## Vendored documentation

`docs/vendored/` holds pinned, read-only third-party manuals that the Root Pack
shipped. Before you write code against one of those libraries, read the page
instead of recalling the API from memory. `docs/vendored/vendored.toml` holds
the pin, the licence and the page to read for each subject, and
`docs/README.md` registers the tree. `pack/configs/prek.toml` excludes the tree
from every hook, so no hook of the gate can repair a local edit there.

Delete the tree and its row in `docs/README.md` in one change when this project
uses none of those libraries.
