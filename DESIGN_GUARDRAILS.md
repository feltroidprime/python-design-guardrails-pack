# Design guardrails

The pack turns a small set of repository-design decisions into checks. It
prescribes no product model: a new project starts with zero Product
Capabilities, and the owner adds the first one.

| Design intent | Enforced by |
|---|---|
| Start without accidental product semantics | The tree ships no product capability. A capability is one directory the owner adds under the package. |
| Keep pack-owned and user-owned files distinct | Two ownership surfaces, stated as one predicate in `pack/scripts/ownership.py`. Pack-owned is `pack/`, plus `_`-prefixed names and `py.typed` in the package. User-owned is everything else. `pack/proof/ownership.toml` owns the law, no file holds a list of ownership roots, and ADR-0008 records the decision. |
| Keep dependency direction explicit | Six `import-linter` contracts in `pack/configs/importlinter.ini` state the capability rules: required layers that point inward, private internals, independent capabilities, a private `_foundation`, and a pure domain. `pack/scripts/import_contracts.py` injects the package name and the discovered capability list, and it holds no rule. |
| Keep the capability layout checkable by a maintained tool | The `capability-layers`, `capability-public-surface`, and `capability-independence` contracts of `import-linter` enforce the layout, so a defect report comes from `import-linter` and never from pack code. |
| Carry current tool policy to a project that already exists | Policy is pack-owned, so a Pack Update replaces whole policy files and writes no user-owned file. It refuses a dirty worktree, a newer project version and any local change to a pack-owned file. It never runs the gate: a red gate on user code afterwards is the intended signal. |
| Require executable evidence for critical decisions | `pack/proof/policy.toml`, the catalogs beside it, `pack/scripts/proof_guard.py`, Hypothesis checks, and bounded CrossHair checks. Discovery is structural: every `*.toml` below `pack/proof/`, and the `proof.toml` of each capability. The policy holds no catalog root and no ownership root, so no list can disagree with the tree. |
| Keep the command surface renderable by the router | `CLI001` to `CLI004` in `pack/scripts/cli_surface.py` check every `<cap>/api.py`, composed or not: a reserved parameter name, a missing docstring, an annotation outside the closed stdlib set, and a `bool` parameter without a `False` default. |
| Keep the command seam pack-owned | `ARCH021` to `ARCH023` in `pack/scripts/cli_discipline.py` target `_foundation/`. `_foundation/router.py` is the one module that can reach an argument parser and the one module that can end the process. |
| Keep the command line derived, never hand-written | `_foundation/router.py` imports one user-owned module, the composition root, and reads its `CAPABILITIES` tuple. Discovery is composition, never a filesystem scan. The router derives each group, subcommand, option, help text, envelope, page and exit code from stdlib-typed signatures and stdlib exceptions, so a capability writes no command-line code and never selects an exit code. |
| Keep routine quality checks consistent | One gate: twelve local hooks in `pack/configs/prek.toml` — `lockfile`, `format`, `lint`, `types`, `dependencies`, `architecture`, `docs`, `proof`, `symbolic`, `import-contracts`, `tests`, `manifest`. `just check` and CI both run `prek run --all-files -c pack/configs/prek.toml`, so a local run and a CI run cannot disagree. `prek.toml` pins Python hooks to 3.14 so their parser matches the repository language contract. |
| Keep every declared dependency used, and every used dependency declared | The `dependencies` hook runs `deptry` over `src` and `pack/scripts`. |
| Keep comments free of scheduled manual upkeep | Ruff's `TD` and `FIX` families. They replace the hand-written upkeep-comment rule and its edit-time hook, so a maintained tool carries the rule instead of pack code. `_foundation/router.py` derives the command surface from the `CAPABILITIES` tuple of `composition.py`, so a separate registration check no longer applies. |
| Make a stale record of the Pack-owned Surface fail early | The `manifest` hook recomputes the sha256 of every pack-owned file and compares it with `pack/manifest.json`. A Pack Update reads that record to find local drift, so a stale record hides a changed file. The hook moves that discovery from update time to commit time. It compares the `root` and `package` lists only, for the reason stated below. |
| Give a new project a CI workflow that it can pass | `.github/workflows/quality.yml` is one of the four starting files that the projection overlays, so a projected workflow holds the `quality` job only. The job for the acceptance suite stays in the pack, with the suite it runs. Assertion `REM-7` runs every marker selection of the projected workflow against the projected tree and fails on any that collects nothing. |
| Keep one project file that both projects can carry | The build backend is `uv_build`, and inclusion is by presence, so `pyproject.toml` holds no include table and no file list. The projection payload is one archive of the last commit, staged inside the package at build time. The gate drops that archive, and `.gitignore` keeps it out of every commit. `pack/tests/test_packaging.py` states the four facts. |
| Prove the whole claim from outside the tree | The acceptance suite proves the packaging and projection claims from an installed console script, because a source checkout can hide a packaging defect. It is marked `acceptance`, the `tests` hook excludes the marker, and a separate CI job runs it (issue #81). Terminal Projection deletes the suite, so no project receives it. |
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

`_foundation/` is pack-owned. A pack-owned catalog needs the package name to
name a target below `src/<pkg>/`, but a pack-owned file must carry no identity
token. Mandatory proof coverage is therefore product behavior, and a capability
declares its own laws in its own user-owned `proof.toml`. A project with no
capability mandates nothing, which is the same fact the `import-contracts` hook
reports.

## One narrowed lint rule: the last handler of the router

`pack/configs/ruff.toml` turns off `BLE001` for one file, `_foundation/router.py`,
because that module's last handler must catch every remaining exception. The
full rationale is in `pack/docs/architecture/EXCEPTIONS.md`.

## One deliberate loosening: no coverage assertion

No coverage assertion exists in this tree or in a projected project. No
coverage flag, coverage plugin, or coverage configuration table is allowed in
either. This section states the rationale, as the change protocol requires
(issue #85).

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

## One packaging rule: the build ships the last commit

The build backend is `uv_build`, and one `pyproject.toml` serves the Root Pack
and every Terminal Project. The backend includes what sits under the module
root, so the file declares no include table and no file list. Inclusion is by
presence, and the file therefore holds no packaging line that exists only for
the pack.

The earlier `hatchling` shape failed on that last point. Its `force-include`
table sat inside the file that projection rewrites, so the table did not erase
itself. Measurement put 8 pack-only lines in each Terminal Project, and 12
duplicated entries in the wheel that the project built (issue #80).

The projection payload is one archive of the last commit, staged inside the
package at build time. The build step stages the archive, builds the wheel,
then deletes the archive.

**A release must commit first.** The archive holds `HEAD`, and never the
working tree. Uncommitted work is absent from the wheel, and the shipped tree is
then the tree of the previous commit.

An interrupted build leaves the archive in the tree, so two rules protect the
gate and the history. `exclude` in `pack/configs/prek.toml` drops the archive
path, and the `manifest` hook ignores the same name, so the finding count of the
gate does not change. `.gitignore` keeps the archive out of every commit.

Two different steps share the name `release`. The `release` function of the
One-shot Bootstrap capability is the build step described above. Assertion
`TER-6` of #81 forbids a pack-only instruction in `pack/justfile`, so the build
step stays inside the capability and disappears with it. The `release` recipe
of `pack/justfile`, by contrast, creates an annotated git tag. It checks the
changelog entry and the working tree first, and it reaches every Terminal
Project.

## Three widened tool entries: a capability is real code

The One-shot Bootstrap is the first Product Capability of this tree, and three
pack-owned entries had to widen for a capability to exist at all. Each glob
holds no package name and no capability name, so a pack update carries it to
every project unchanged.

| Entry | Widening | Why |
|---|---|---|
| `pack/configs/pytest.ini` | `testpaths` gains `src` | A capability's tests sit inside the capability. Without this entry they are never collected, and the `acceptance` marker of the `tests` hook has nothing to exclude. |
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
real trees. That comparison is the acceptance suite, run from the installed
console script, and it lives in the acceptance directory of the same capability
(issue #81).

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

Two ordinary events make the current bytes of a shim differ from that record.
Neither one fails the gate, because the hook never compares `shims`.

- The `justfile` carries one comment that asks its owner to add recipes below
  the import. Each recipe an owner adds changes the file's bytes.
- Terminal Projection overlays `.github/workflows/quality.yml` with one of the
  starting files. `pack/manifest.json` is projected verbatim, so its `shims`
  entry still records the pack's own bytes for that file, not the overlaid ones.

The alternative was to keep the comparison and stop overlaying the workflow.
That leaves a defect in place (issue #118): the acceptance job survives in a
project that holds no acceptance test, and exit code 5 fails it forever.

Nothing replaces the comparison, because the `shims` list was never evidence
about the current tree. The pack-owned comparison is unchanged, `verify` still
reads the `shims` list and still fails a manifest that omits it, and assertion
`UPD-13` still proves that an update reports a customised shim and writes none.

## One pack-owned ignore rule: `pack/.gitignore`

A forced Pack Update saves the pack-owned bytes it replaces under
`pack/.drift/<path>`, and that directory must stay out of git. The rule lives in
a new pack-owned `pack/.gitignore`, never in the root `.gitignore` (issue #85).

The root file is user-owned and frozen at init, so a rule written there reaches
no existing project. A rule under `pack/` is replaced whole by every later
update, which is exactly what makes it reach one. The gate reads the same
exclusion twice more, in the `exclude` pattern of `pack/configs/prek.toml` and
in the ignore list of `pack/scripts/manifest_guard.py`, because a backup is
recovery material and never release content.
