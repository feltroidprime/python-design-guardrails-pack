# Design guardrails

The pack turns a small set of repository-design decisions into checks. It does
not prescribe a product model: N0 contains a control plane and an empty product
baseline.

| Design intent | Enforced by |
|---|---|
| Start without accidental product semantics | `architecture.toml` declares product roots while the template owns no product capability; `tests/test_ownership_zones.py` verifies that product source roots are absent and that `repoctl/` is the only shipped control root. |
| Keep template, owner, and generated output distinct | Ownership zones in `architecture.toml`, `scripts/ownership_guard.py`, and `scripts/architecture_guard.py`. |
| Keep dependency direction explicit | Import Linter contracts, the architecture guard, and package entry points. |
| Make repository evolution inspectable | `repoctl/` owns repository-generation plans, declarations, lifecycle decisions, and the machine-readable command protocol. |
| Require executable evidence for critical decisions | `proof/policy.toml`, proof catalogs, `scripts/proof_guard.py`, Hypothesis checks, and bounded CrossHair checks. |
| Keep generated indexes replaceable | `_generated/` is an ownership zone with deterministic compilation and empty N0 indexes. |
| Keep routine quality checks consistent | `just check`, prek hooks, and the generated quality gate run formatting, linting, type checks, ownership, architecture, documentation, imports, tests, and coverage. |
| Certify recursive self-generation and teach only the exercised workflow | `tests/recursive/test_recursive_generation.py` drives one real N0 → N1 → N2 walk through `repoctl` and checks the downstream agent workflow against its ordered invocation log; `just test` isolates that subprocess-heavy walk, then runs the generated-gate matrix separately from the lightweight remainder so they do not contend, keeping the complete pre-push suite within a seven-minute warm-cache budget while pre-commit stays sub-minute. |
| Keep the architecture neutral across representative application shapes | `tests/recursive/test_shape_*.py` creates pure-library, stateful-workflow, CLI, external-integration, and multi-capability-composition fixtures through the real repository CLI. |
| Keep the required fault model tied to deterministic evidence | `tests/fixtures/mutation_catalog.json` maps all fourteen specification mutations to existing killers, and `tests/mutations/test_mutation_catalog.py` checks exact coverage, order, identifiers, mechanisms, commands, and collected tests. |
| Prevent stale documentation from teaching a removed product model | `scripts/docs_guard.py` checks generated documentation paths and registry entries; `tests/test_instantiate.py::test_root_and_template_markdown_contain_no_removed_product_vocabulary` rejects retired exemplar vocabulary across root and template Markdown. |
| Detect accidental template regressions | `tests/test_instantiate.py::test_expected_files_are_preserved` checks the N0 file contract; `just validate` renders a fresh repository and runs its full gate. |

These checks are intentionally structural. They make ownership and evidence
visible, while names, product behavior, and worthwhile abstractions remain
engineering decisions for the repository owner.
