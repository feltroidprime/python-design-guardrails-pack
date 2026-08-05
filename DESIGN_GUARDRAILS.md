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
| Require executable evidence for critical decisions | `proof/policy.toml`, proof catalogs, `scripts/proof_guard.py`, Hypothesis checks, and bounded CrossHair checks. |
| Keep generated indexes replaceable | `_generated/` is an ownership zone with deterministic compilation and empty N0 indexes. |
| Keep routine quality checks consistent | One gate: twelve local hooks in `pack/configs/prek.toml` — `lockfile`, `format`, `lint`, `types`, `dependencies`, `architecture`, `docs`, `proof`, `symbolic`, `import-contracts`, `tests`, `manifest`. `just check` and CI both run `prek run --all-files -c pack/configs/prek.toml`, so a local run and a CI run cannot disagree. `prek.toml` pins Python hooks to 3.14 so their parser matches the repository language contract. |
| Keep every declared dependency used, and every used dependency declared | The `dependencies` hook runs `deptry` over `src` and `pack/scripts`. |
| Keep comments free of scheduled manual upkeep | Ruff's `TD` and `FIX` families. They replace the hand-written upkeep-comment rule and its edit-time hook, so a maintained tool carries the rule instead of pack code. The two command-registration rules also go: the router derives the command surface, so no catalog registration remains to guard. |
| Make a stale record of the Pack-owned Surface fail early | The `manifest` hook recomputes the sha256 of every pack-owned file and compares it with `pack/manifest.json`. A Pack Update reads that record to find local drift, so a stale record would hide a changed file. The hook moves that discovery from update time to commit time. |
| Certify recursive self-generation and teach only the exercised workflow | `tests/recursive/test_recursive_generation.py` drives one real N0 → N1 → N2 walk through `repoctl` and checks the downstream agent workflow against its ordered invocation log; `just test` isolates that subprocess-heavy walk, then runs the generated-gate matrix separately from the lightweight remainder so they do not contend, keeping the complete pre-push suite within a seven-minute warm-cache budget while pre-commit stays sub-minute. |
| Keep the architecture neutral across representative application shapes | `tests/recursive/test_shape_*.py` creates pure-library, stateful-workflow, CLI, external-integration, and multi-capability-composition fixtures through the real repository CLI. |
| Keep the required fault model tied to deterministic evidence | `tests/fixtures/mutation_catalog.json` maps all fourteen specification mutations to existing killers, and `tests/mutations/test_mutation_catalog.py` checks exact coverage, order, identifiers, mechanisms, commands, and collected tests. |
| Prevent stale documentation from teaching a removed product model | `scripts/docs_guard.py` checks generated documentation paths and registry entries; `tests/test_instantiate.py::test_root_and_template_markdown_contain_no_removed_product_vocabulary` rejects retired exemplar vocabulary across root and template Markdown. |
| Detect accidental template regressions | `tests/test_instantiate.py::test_expected_files_are_preserved` checks the N0 file contract; `just validate` renders a fresh repository and runs its full gate. |

These checks are intentionally structural. They make ownership and evidence
visible, while names, product behavior, and worthwhile abstractions remain
engineering decisions for the repository owner.

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
