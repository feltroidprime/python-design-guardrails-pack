# Design guardrails

The pack turns a small set of repository-design decisions into checks. It does
not prescribe a product model: N0 contains a control plane and an empty product
baseline.

| Design intent | Enforced by |
|---|---|
| Start without accidental product semantics | The tree ships no product capability. A capability is one directory the owner adds under the package. |
| Keep pack-owned and user-owned files distinct | Two ownership zones, stated as one predicate in `pack/scripts/ownership.py`. Pack-owned is `pack/`, plus `_`-prefixed names and `py.typed` in the package. User-owned is everything else. `pack/proof/ownership.toml` owns the law, and no file holds a list of ownership roots. |
| Keep dependency direction explicit | Six `import-linter` contracts in `pack/configs/importlinter.ini` carry capability rules L1 to L4: required layers that point inward, private internals, independent capabilities, a private `_foundation`, and a pure domain. `pack/scripts/import_contracts.py` injects the package name and the discovered capability list, and it holds no rule. |
| Keep the capability layout checkable by a maintained tool | The three hand-written capability rules are gone. Each one is now a contract, so a defect report comes from `import-linter` rather than from pack code. |
| Make repository evolution inspectable | `repoctl/` owns repository-generation plans, declarations, lifecycle decisions, and the machine-readable command protocol. |
| Require executable evidence for critical decisions | `pack/proof/policy.toml`, the proof catalogs, `pack/scripts/proof_guard.py`, Hypothesis checks, and bounded CrossHair checks. Catalog discovery is structural: every `*.toml` below `pack/proof/`, and the `proof.toml` of each capability. The policy holds no catalog root and no ownership zone, so no list can disagree with the tree. |
| Keep the command surface renderable by the router | `CLI001` to `CLI004` in `pack/scripts/cli_surface.py` check every `<cap>/api.py`, composed or not: a reserved parameter name, a missing docstring, an annotation outside the closed stdlib set, and a `bool` parameter without a `False` default. |
| Keep the command seam pack-owned | `ARCH021` to `ARCH023` in `pack/scripts/cli_discipline.py` target `_foundation/`. `_foundation/router.py` is the one module that may reach an argument parser and the one module that may end the process. |
| Keep the command line derived, never hand-written | `_foundation/router.py` imports one user-owned module, the composition root, and reads its `CAPABILITIES` tuple. Discovery is composition, never a filesystem scan. The router derives each group, subcommand, option, help text, envelope, page and exit code from stdlib-typed signatures and stdlib exceptions, so a capability writes no command-line code and never selects an exit code. |
| Keep routine quality checks consistent | One gate: twelve local hooks in `pack/configs/prek.toml` — `lockfile`, `format`, `lint`, `types`, `dependencies`, `architecture`, `docs`, `proof`, `symbolic`, `import-contracts`, `tests`, `manifest`. `just check` and CI both run `prek run --all-files -c pack/configs/prek.toml`, so a local run and a CI run cannot disagree. `prek.toml` pins Python hooks to 3.14 so their parser matches the repository language contract. |
| Keep every declared dependency used, and every used dependency declared | The `dependencies` hook runs `deptry` over `src` and `pack/scripts`. |
| Keep comments free of scheduled manual upkeep | Ruff's `TD` and `FIX` families. They replace the hand-written upkeep-comment rule and its edit-time hook, so a maintained tool carries the rule instead of pack code. The two command-registration rules also go: the router derives the command surface, so no catalog registration remains to guard. |
| Make a stale record of the Pack-owned Surface fail early | The `manifest` hook recomputes the sha256 of every pack-owned file and compares it with `pack/manifest.json`. A Pack Update reads that record to find local drift, so a stale record would hide a changed file. The hook moves that discovery from update time to commit time. |
| Keep one project file that both projects can carry | The build backend is `uv_build`, and inclusion is by presence, so `pyproject.toml` holds no include table and no file list. The projection payload is one archive of the last commit, staged inside the package at build time. The gate drops that archive, and `.gitignore` keeps it out of every commit. `pack/tests/test_packaging.py` states the four facts. |
| Certify recursive self-generation and teach only the exercised workflow | `tests/recursive/test_recursive_generation.py` drives one real N0 → N1 → N2 walk through `repoctl` and checks the downstream agent workflow against its ordered invocation log; `just test` isolates that subprocess-heavy walk, then runs the generated-gate matrix separately from the lightweight remainder so they do not contend, keeping the complete pre-push suite within a seven-minute warm-cache budget while pre-commit stays sub-minute. |
| Keep the architecture neutral across representative application shapes | `tests/recursive/test_shape_*.py` creates pure-library, stateful-workflow, CLI, external-integration, and multi-capability-composition fixtures through the real repository CLI. |
| Keep the required fault model tied to deterministic evidence | `tests/fixtures/mutation_catalog.json` maps all fourteen specification mutations to existing killers, and `tests/mutations/test_mutation_catalog.py` checks exact coverage, order, identifiers, mechanisms, commands, and collected tests. |
| Prevent stale documentation from teaching a removed product model | `scripts/docs_guard.py` checks generated documentation paths and registry entries; `tests/test_instantiate.py::test_root_and_template_markdown_contain_no_removed_product_vocabulary` rejects retired exemplar vocabulary across root and template Markdown. |
| Detect accidental template regressions | `tests/test_instantiate.py::test_expected_files_are_preserved` checks the N0 file contract; `just validate` renders a fresh repository and runs its full gate. |

These checks are intentionally structural. They make ownership and evidence
visible, while names, product behavior, and worthwhile abstractions remain
engineering decisions for the repository owner.

## One re-aimed guardrail: the mandatory proof root

A behavior root is where the proof guard demands a property or an exemption. It
was `_foundation/`. It is now the `domain/` and `application/` layer of each
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

The `proof.toml` of the One-shot Bootstrap exempts all 21 of its public
behaviors rather than proving them. This is the one such catalog in the tree,
and the reason is the shape of the behavior, not its difficulty.

Terminal Projection is a whole-tree effect. Its laws are byte parity between two
trees, the absence of a token, the absence of a directory, and an overlay that
only replaces. None of them is observable in one generated example, and all of
them are observable in one comparison of two real trees. That comparison is the
acceptance suite of #81: 53 assertions, run from the installed console script,
which ticket I10 writes into the acceptance directory of the same capability.

Each exemption carries a revisit date. Terminal Projection deletes the
capability, so neither the catalog nor the suite reaches a user's project.
