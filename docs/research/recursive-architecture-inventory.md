# Inventory of the recursive architecture to delete

Status: research note, 2026-07-31. Resolves
[Inventory the recursive architecture to delete](https://github.com/feltroidprime/python-design-guardrails-pack/issues/87),
a ticket of the map
[Wayfind the self-hosting Root Pack and Terminal Project](https://github.com/feltroidprime/python-design-guardrails-pack/issues/79).
This note records findings. It changes no contract and no code.

## Question

Which code, configuration, tests, documentation, packaging surfaces, and
vocabulary exist only to support the parallel `template/` tree, Copier,
`repoctl`, N0/N1/N2 recursion, plans, declarations, lifecycle state, or
generated capability indexes; and which guardrails are genuinely reusable in
the target model?

## Method

Three inventories covered the tracked tree in full. Every file received exactly
one verdict: DELETE, REWRITE, KEEP, IDENTITY, or MOVE-TO-BOOTSTRAP. Detail,
with `path:line` citations, is in the three companion notes:

- [Root generation and packaging surface](inventory-root-surface.md) —
  `instantiate.py`, `copier.yml`, root `pyproject.toml`, `justfile`,
  `prek.toml`, `scripts/`, `.github/`, root documents, `epics/`.
- [The `template/` tree](inventory-template-tree.md) — all 157 files.
- [`tests/`, `docs/`, `.agents/`, `.claude/`](inventory-tests-and-docs.md).

## Answer in one paragraph

About half of the product tree is recursion machinery. Under `template/`, 76 of
157 files are DELETE and 34 are REWRITE; 47 files are reusable guardrails.
`repoctl` loses 32 of its 34 files. Every declaration file, lifecycle state,
registry, generated capability index, and plan disappears, together with the
tests and proof laws that police them. The guardrails themselves — the quality
gate, the 28 architecture rules, the ownership map, the capability contract, the
proof-catalog closure engine, and the documentation rules — survive almost
unchanged. Most rewrites are mechanical: a test that renders
`architecture.toml.jinja` into a temporary directory instead reads the real
`architecture.toml`. Three decisions block a clean cut, and they are listed at
the end.

## What dies

### The generator and the second tree

- `copier.yml` in full, and the Copier answers file template.
- `instantiate.py` as a Copier adapter, including the legacy positional
  `main()` that exists only for `scripts/validate_pack.py`.
- The `template/` prefix itself, the `.jinja` suffix on 157 paths, hatchling
  `force-include "template"`, and Copier `_commit` provenance.
- In `scripts/validate_pack.py`: `find_forbidden_artifacts`,
  `find_unrendered_jinja`, and the `_exclude` parser.
- In `tests/test_instantiate.py`: Copier answers and provenance, Jinja scans,
  delta-or-identical toggles, worktree and dirty-tag generation.

### The control plane

- `repoctl/`: 32 of 34 files — the CLI (511 lines), the mutation CLI (638
  lines), the plan model, the planner, the decision model, the journal, the
  lifecycle `activate` and `retire` commands, `compile_indexes`, the
  declaration decoder, and the local and in-memory repository ports.
- Declarations: `.repo/repository.toml` and `.repo/capabilities/*.toml`.
- Generated capability indexes: `src/<package>/_generated/` (4 files) and
  `proof/_generated/index.json`, both carrying a `source-state-sha256`.
- Five of six `REPOCTL::` proof laws: apply-idempotent, stale-plan,
  product-bytes, commute, derived-index-exact, plan-deterministic.
- The evidence for all of it: `tests/repoctl/` (15 files),
  `verification/repoctl/` (7), `tests/unit/generated/`, `tests/foundation/`.
- `src/<package>/adapters/` (5 files), retained today only because `repoctl`
  imports them.

### The recursion proofs

- `tests/recursive/` in full: the nineteen-step N0 → N1 → N2 walk and
  `harness.py`, which drives `repoctl` as a subprocess.
- `tests/scale/`: benchmarks over 100 declarations and command commutativity.
  No commands survive.
- `tests/fixtures/capability_seed/` (already dead) and
  `tests/fixtures/performance_budgets.json`.
- `tests/test_root_ruff_policy.py` and `tests/test_selfhost_validator.py`, both
  of which prove parity between two trees that become one.

### Documents

- `epics/SPEC-0001.md` (1475 lines, "Recursive Proof-Carrying Repository"),
  ADR-0002, ADR-0004, and `epics/epic-1..5.yaml`.
- In root `AGENTS.md`, the "Two contracts, do not confuse them" section. It is
  the organizing idea of the document, and one tree means one contract.

## What survives

47 guardrails are reusable. The full numbered list is in the template
inventory; the groups are:

| Guardrail group | Enforced today by |
|---|---|
| Quality gate: 11 checks, syntax pre-check, self-repairing prek hooks, CI mirror, doctor | `template/scripts/quality_gate.py.jinja` (256 lines, no Jinja) |
| Ruff, BasedPyright, pytest, 90% coverage floor | `template/pyproject.toml.jinja` |
| 28 architecture rules: size ceilings, domain purity, immutable dataclasses, ADR-backed suppressions, None/path/override/review discipline | `architecture.toml.jinja` + `architecture_rules.py` |
| Ownership map: no overlapping roots, single-owner classification (OWN001–OWN004) | `ownership*.py` |
| Capability contract CAP001–CAP003 | `capability_validator.py` |
| Proof-catalog closure engine (18 modules), CrossHair canary, Hypothesis profiles | `template/scripts/proof/` |
| Documentation rules DOC001–DOC007 | `docs_guard.py` |
| Session evidence capture | `agent_sessions.py` |

CAP001–CAP003 are the most important finding: they already describe the
filesystem-native Product Capability — `api.py` plus `domain/`, `application/`,
and `adapters/{inbound,outbound}/`, with layer direction enforced and imports
routed through `api`. The target contract does not have to be invented. It has
to be freed from the declaration file that currently accompanies it.

Seven proofs must survive in some form:

1. A Pack Update never rewrites a User-owned byte.
2. The pack ships nothing into user-owned roots.
3. Terminal Projection changes only identity fields and removes only the
   One-shot Bootstrap. This one is new; it replaces the delta-or-identical
   tests.
4. ARCH016–ARCH031, DOC001–DOC007, the proof contract, and the CrossHair gate,
   with unchanged bodies.
5. Each capability shape passes the full gate and exposes only `api`.
   Re-expressed as checked-in example capabilities instead of fixtures.
6. The documented workflow equals the executed workflow.
7. Mutation entries name a deterministic killer; pins cohere; hooks are tiered;
   `release.py` refuses an unrecorded version.

## The rewrites are mostly mechanical

Six suites — `test_cli_discipline`, `test_none_discipline`,
`test_path_discipline`, `test_review_discipline`, `test_docs_guard`, and
`test_ownership_zones` — read their policy by rendering
`architecture.toml.jinja` into a `tmp_path`. Every rule body survives verbatim.
Only the fixture changes: read the real `architecture.toml`.

The same pattern holds for 22 `.jinja` files that substitute nothing but
`package` and `project_name`, and for 5 `.jinja` files that contain no Jinja at
all. They become verbatim files.

## Entanglements to fix, not delete

Three imports tie a surviving guardrail to the dying generator:

1. `template/scripts/ownership.py:6` imports the repository path classifier from
   `repoctl.modules.repository_generation.api`. The classifier must move out of
   the generator.
2. `template/scripts/capability_validator.py:309` hard-codes `repoctl/modules`
   as a FOUNDATION capability parent.
3. `architecture.toml.jinja:54-59` declares the `DERIVED` and `DECLARATION`
   ownership zones, and `ownership_guard.py:33` pins all four zone names. The
   target has two surfaces, not four zones.

## Root-only guardrails that must become ordinary guardrails

The root runs only Ruff and pytest on itself today.
`pyproject.toml:204-208` excludes `template` from BasedPyright. Type checking,
coverage, architecture, ownership, docs, proof, Import Linter, and CrossHair run
only downstream. A self-hosting Root Pack must run all of them on itself,
including on the One-shot Bootstrap capability code.

The root is also deliberately venv-less and lock-free: `justfile:8-10` uses
`uv run --no-project --with`, and `.gitignore:8-10` ignores `uv.lock`. That
premise dies. The Root Pack needs a real environment and a lockfile.

## Vocabulary to retire

Consolidated from the three inventories. `repoctl` appears in 18 files under
`tests/` alone; `template` and `TEMPLATE_ROOT` appear in every guard fixture.

| Retire | Use |
|---|---|
| meta-repository, template tree | Root Pack |
| generated repository, downstream, N0 | Terminal Project |
| generate, instantiate, template rendering | Terminal Projection |
| recursive generation, self-replication | One-shot Bootstrap |
| scaffold-update, self-update | Pack Update |
| ownership zones (four) | Pack-owned Surface, User-owned Surface |
| registered capability, child repository | Product Capability |
| repoctl, plan, declaration, lifecycle, registry, `_generated/` index, N0 → N1 → N2, Copier, Jinja, `vcs_ref`, `_commit` | no replacement — the concept goes |

`tests/test_instantiate.py:1206` already machine-enforces a removed-vocabulary
list. Re-point it at the `_Avoid_` terms in `CONTEXT.md`.

## Decisions this inventory cannot make

These three block a clean cut and belong to other tickets or to the map.

1. **`agents_contract` and `workspace_member` are real rendering variants**
   (`copier.yml:41-57`), not project identity. CONTEXT.md permits substituting
   only a closed set of identity fields, so Terminal Projection cannot stay
   byte-identical while keeping them. Either fix both at the Root Pack and lose
   the variants, or widen the identity field set. This is projection-contract
   work.
2. **The four ownership zones versus two surfaces.** Whether Pack-owned and
   User-owned fully replace SYSTEM, PRODUCT, DERIVED, and DECLARATION is
   partition work.
3. **How a Pack Update is tested without a second tree**, and what replaces the
   seven deleted control-plane mutations in the mutation catalog. This is
   acceptance-criteria work.

Two smaller items: whether the capability shape examples ship into a Terminal
Project, and `epics/epic-1.yaml:282`, which still describes a fixture that is
already dead.
