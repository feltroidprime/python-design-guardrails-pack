# Design guardrails

The pack turns a small set of repository-design decisions into checks. It
prescribes no product model: a new project starts with zero Product
Capabilities, and the owner adds the first one.

| Design intent | Enforced by |
|---|---|
| Start without accidental product semantics | The tree ships no product capability. A capability is one directory the owner adds under the package. |
| Keep pack-owned and user-owned files distinct | Two ownership surfaces, stated as one predicate in `pack/scripts/ownership.py`. Pack-owned is `pack/`, plus `_`-prefixed names and `py.typed` in the package. User-owned is everything else. `pack/proof/ownership.toml` owns the law, no file holds a list of ownership roots, and ADR-0008 records the decision. |
| Keep dependency direction explicit | Six `import-linter` contracts in `pack/configs/importlinter.ini` carry capability rules L1 to L4: required layers that point inward, private internals, independent capabilities, a private `_foundation`, and a pure domain. `pack/scripts/import_contracts.py` injects the package name and the discovered capability list, and it holds no rule. |
| Keep the capability layout checkable by a maintained tool | The three hand-written capability rules are gone. Each one is now a contract, so a defect report comes from `import-linter` rather than from pack code. |
| Carry current tool policy to a project that already exists | Policy is pack-owned, so a Pack Update replaces whole policy files and writes no user-owned file. It refuses a dirty worktree, a newer project version and any local change to a pack-owned file. It never runs the gate: a red gate on user code afterwards is the intended signal. |
| Require executable evidence for critical decisions | `pack/proof/policy.toml`, the catalogs beside it, `pack/scripts/proof_guard.py`, Hypothesis checks, and bounded CrossHair checks. Discovery is structural: every `*.toml` below `pack/proof/`, and the `proof.toml` of each capability. The policy holds no catalog root and no ownership root, so no list can disagree with the tree. |
| Keep the command surface renderable by the router | `CLI001` to `CLI004` in `pack/scripts/cli_surface.py` check every `<cap>/api.py`, composed or not: a reserved parameter name, a missing docstring, an annotation outside the closed stdlib set, and a `bool` parameter without a `False` default. |
| Keep the command seam pack-owned | `ARCH021` to `ARCH023` in `pack/scripts/cli_discipline.py` target `_foundation/`. `_foundation/router.py` is the one module that may reach an argument parser and the one module that may end the process. |
| Keep the command line derived, never hand-written | `_foundation/router.py` imports one user-owned module, the composition root, and reads its `CAPABILITIES` tuple. Discovery is composition, never a filesystem scan. The router derives each group, subcommand, option, help text, envelope, page and exit code from stdlib-typed signatures and stdlib exceptions, so a capability writes no command-line code and never selects an exit code. |
| Keep routine quality checks consistent | One gate: twelve local hooks in `pack/configs/prek.toml` — `lockfile`, `format`, `lint`, `types`, `dependencies`, `architecture`, `docs`, `proof`, `symbolic`, `import-contracts`, `tests`, `manifest`. `just check` and CI both run `prek run --all-files -c pack/configs/prek.toml`, so a local run and a CI run cannot disagree. `prek.toml` pins Python hooks to 3.14 so their parser matches the repository language contract. |
| Keep every declared dependency used, and every used dependency declared | The `dependencies` hook runs `deptry` over `src` and `pack/scripts`. |
| Keep comments free of scheduled manual upkeep | Ruff's `TD` and `FIX` families. They replace the hand-written upkeep-comment rule and its edit-time hook, so a maintained tool carries the rule instead of pack code. The two command-registration rules also go: the router derives the command surface, so no catalog registration remains to guard. |
| Make a stale record of the Pack-owned Surface fail early | The `manifest` hook recomputes the sha256 of every pack-owned file and compares it with `pack/manifest.json`. A Pack Update reads that record to find local drift, so a stale record would hide a changed file. The hook moves that discovery from update time to commit time. It compares the `root` and `package` lists only, for the reason stated below. |
| Give a new project a CI workflow that it can pass | `.github/workflows/quality.yml` is one of the four starting files that the projection overlays, so a projected workflow holds the `quality` job only. The job for the acceptance suite stays in the pack, with the suite it runs. Assertion `REM-7` runs every marker selection of the projected workflow against the projected tree and fails on any that collects nothing. |
| Keep one project file that both projects can carry | The build backend is `uv_build`, and inclusion is by presence, so `pyproject.toml` holds no include table and no file list. The projection payload is one archive of the last commit, staged inside the package at build time. The gate drops that archive, and `.gitignore` keeps it out of every commit. `pack/tests/test_packaging.py` states the four facts. |
| Prove the whole claim from outside the tree | The acceptance suite carries the 53 assertions of #81. It is marked `acceptance`, the `tests` hook excludes the marker, and a separate CI job runs it. Every assertion runs from an installed console script, because a source checkout hides a packaging defect. Terminal Projection deletes the suite, so no project receives it. |
| Keep the architecture neutral across representative application shapes | The suite builds a pure-library, a stateful-workflow, a CLI, an external-integration and a multi-capability shape from its own fixtures, and runs the one gate over each. |
| Keep the required fault model tied to deterministic evidence | `pack/tests/fixtures/mutation_catalog.json` maps each surviving specification mutation to an existing killer, and `pack/tests/mutations/test_mutation_catalog.py` checks exact coverage, order, identifiers, mechanisms, commands and collected tests. |
| Prevent stale documentation from teaching a removed model | `pack/scripts/docs_guard.py` checks every path a document claims, every ADR convention, and the registration of every document in `docs/README.md`. The acceptance suite adds two word searches: one over identifiers and one over the retired prose that `CONTEXT.md` names. |

These checks are intentionally structural. They make ownership and evidence
visible, while names, product behavior, and worthwhile abstractions remain
engineering decisions for the repository owner.

## One re-aimed guardrail: the mandatory proof root

A behavior root is where the proof guard demands a property or an exemption. It
was `_foundation/`. It is now the domain and application layer of each
discovered capability.

`_foundation/` is pack-owned. A pack-owned catalog would have to write the
package name to name a target below `src/<pkg>/`, and invariant O1 of #85
forbids an identity token in a pack-owned file. Mandatory proof coverage is
therefore product behavior, and a capability declares its own laws in its own
user-owned `proof.toml`. A project with no capability mandates nothing, which is
the same fact the `import-contracts` hook reports.

## One narrowed lint rule: the last handler of the router

`pack/configs/ruff.toml` turns `BLE001` off for one file, `_foundation/router.py`.
The exception table of #85 section 3.1 ends with a row that reads "anything
else", and the router answers that row with the `unexpected_failure` envelope
and exit 70. A handler that catches every remaining exception is therefore the
rule in that one module, and it is the reason a capability never has to select
an exit code. The entry uses a directory glob, so it holds no package name and a
pack update carries it to every project.

## One deliberate loosening: no coverage assertion

No coverage assertion exists in this tree or in a projected project. No
coverage flag, coverage plugin, or coverage configuration table is allowed in
either. Conflict C10 of #85 settles it, and this section is the rationale that
#85 requires.

A branch-coverage floor measures which lines a test ran, not which behavior a
test proved. The tree already carries stronger evidence for the decisions that
matter: the proof catalog, bounded Hypothesis properties, a symbolic core, and a
mutation catalog that must name a deterministic killer for each specification
mutation. A floor beside those measures adds a number that a test can raise
without proving anything, and it makes a legal work-in-progress capability fail
its own gate.

Nothing replaces the floor. Assertion `LEG-1` searches both trees for the
coverage flag, the coverage plugin and the coverage configuration table, so the
loosening is itself checked.

## Two identifiers removed from the ban list

Assertion `LEG-1` searches both trees for the identifiers of the deleted
architecture. Section 1.5 of #85 wrote that list, and two entries of it name
files that the same specification keeps.

- `schema_version` is the first key of `pack/proof/policy.toml`, of every proof
  catalog, of the `proof.toml` of each capability, and of the machine envelope
  that `_foundation/cli_protocol.py` writes.
- `proof_catalog` names three surviving modules of `pack/scripts/`, and ten more
  files import them.

Section 1.2 of #85 gives each of those files a surviving verdict. A deletion
boundary cannot keep a file and ban its name at the same time, so one of the two
clauses had to give way, and the ban list is the one that did. The deleted
artifact that both entries aimed at is the derived index, whose own first key
was `schema_version`. The list still bans the name of the directory that held
that index, and that entry proves the index is gone, so the list loses no proof
of deletion.

The alternative was a rename: a new key in every catalog and every `proof.toml`,
and a new field in a published envelope. That is a product change, and it would
prove nothing about deletion. The acceptance suite records the same reasoning
beside the list it holds.

## One packaging rule: the build ships the last commit

The build backend is `uv_build`, and one `pyproject.toml` serves the Root Pack
and every Terminal Project. The backend includes what sits under the module
root, so the file declares no include table and no file list. Inclusion is by
presence, and the file therefore holds no packaging line that exists only for
the pack.

The earlier `hatchling` shape failed on that last point. Its `force-include`
table sat inside the file that projection rewrites, so the table could not erase
itself. Measurement put 8 pack-only lines in each Terminal Project, and 12
duplicated entries in the wheel that the project built (#80).

The projection payload is one archive of the last commit, staged inside the
package at build time. The release step stages the archive, builds the wheel,
then deletes the archive.

**A release must commit first.** The archive holds `HEAD`, and never the
working tree. Uncommitted work is absent from the wheel, and the shipped tree is
then the tree of the previous commit.

An interrupted build leaves the archive in the tree, so two rules protect the
gate and the history. `exclude` in `pack/configs/prek.toml` drops the archive
path, and the `manifest` hook ignores the same name, so the finding count of the
gate does not change. `.gitignore` keeps the archive out of every commit.

The release step belongs to the One-shot Bootstrap capability, and never to a
`just` recipe. A recipe in `pack/justfile` reaches every Terminal Project, and
assertion TER-6 of #81 forbids a pack-only instruction there. The `release`
function of that capability is the step, and it disappears with the capability.

## Three widened tool entries: a capability is real code

The One-shot Bootstrap is the first Product Capability of this tree, and three
pack-owned entries had to widen for a capability to exist at all. Each glob
holds no package name and no capability name, so a pack update carries it to
every project unchanged.

| Entry | Widening | Why |
|---|---|---|
| `pack/configs/pytest.ini` | `testpaths` gains `src` | Rule L1 of #85 puts a capability's tests inside the capability. Without this they are never collected, and the `acceptance` marker of the `tests` hook has nothing to exclude. |
| `pack/configs/ruff.toml` | `src/*/*/tests/**` gains `ANN201`, `S101`, `S603`, `S607`; `src/*/*/adapters/outbound/commands.py` gains `S603` | A capability's tests are tests: they assert, and they drive real local tools. The pack's own tests carry the first two entries already. |
| `pack/configs/prek.toml` | the `dependencies` hook excludes `src/*/*/tests` | A test imports the test tools of the development group, which `deptry` reads as a misplaced dependency inside `src/`. |

The one narrowing worth naming is `S603` on one module. A capability reaches an
external program through one outbound adapter, and starting a process is that
module's whole job. `shutil.which` resolves the program before it runs, so the
partial-path rule still applies to every other module of every project.

## One proof catalog of exemptions: the capability that has no unit

The `proof.toml` of the One-shot Bootstrap exempts all 48 of its public
behaviors rather than proving them. This is the one such catalog in the tree,
and the reason is the shape of the behavior, not its difficulty.

Terminal Projection is a whole-tree effect. Its laws are byte parity between two
trees, the absence of a token, the absence of a directory, and an overlay that
only replaces. Pack Update is the same shape: its laws are 0 changed user-owned
bytes, an idempotent second run, a tree that a crash leaves unchanged, and a
write plan that the ownership predicate admits. None of them is observable in
one generated example, and all of them are observable in one comparison of two
real trees. That comparison is the acceptance suite of #81: 53 assertions, run
from the installed console script, which ticket I10 writes into the acceptance
directory of the same capability.

Each exemption carries a revisit date. Terminal Projection deletes the
capability, so neither the catalog nor the suite reaches a user's project.

## One narrowed guardrail: the `manifest` hook and the four shims

`pack/manifest.json` holds three hash lists. The `manifest` hook compares two of
them, `root` and `package`. It does not compare `shims`, and this section is the
rationale that the change protocol requires.

The two compared lists state the Pack-owned Surface, which is what a stale
record hides from a Pack Update. The third list states something else: the
as-shipped bytes of the four user-owned entry points, which an update reads to
tell a customised shim from an untouched one, and never writes. That record is
history, not a claim about the current tree.

Two ordinary events make the current bytes of a shim differ from that record,
and neither one is drift.

- The `justfile` carries one comment that asks its owner to add recipes below
  the import. The first recipe they add would fail the gate.
- Terminal Projection overlays `.github/workflows/quality.yml` with one of the
  starting files, and `pack/manifest.json` is projected verbatim. Every new
  project would be red on the day it is born.

The alternative was to keep the comparison and stop overlaying the workflow.
That leaves the defect of #118 in place: the acceptance job survives in a
project that holds no acceptance test, and exit code 5 fails it forever.

Nothing replaces the comparison, because the `shims` list was never evidence
about the current tree. The pack-owned comparison is unchanged, `verify` still
reads the `shims` list and still fails a manifest that omits it, and assertion
`UPD-13` still proves that an update reports a customised shim and writes none.

## One pack-owned ignore rule: `pack/.gitignore`

A forced Pack Update saves the pack-owned bytes it replaces under
`pack/.drift/<path>`, and that directory must stay out of git. The rule lives in
a new pack-owned `pack/.gitignore`, never in the root `.gitignore` (conflict C11
of #85).

The root file is user-owned and frozen at init, so a rule written there reaches
no existing project. A rule under `pack/` is replaced whole by every later
update, which is exactly what makes it reach one. The gate reads the same
exclusion twice more, in the `exclude` pattern of `pack/configs/prek.toml` and
in the ignore list of `pack/scripts/manifest_guard.py`, because a backup is
recovery material and never release content.
