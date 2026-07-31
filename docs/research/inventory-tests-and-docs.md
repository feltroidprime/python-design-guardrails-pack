# Inventory: `tests/`, `docs/`, `.agents/`, `.claude/`

Status: research inventory for the Root Pack change. Scope: `tests/` (69 tracked
files), `docs/` (407 files, of which 403 are the vendored pin), and the
agent-facing trees `.agents/` and `.claude/`.

## Summary

Two thirds of `tests/` exists to prove that a second tree renders correctly into
a third tree. Of 69 tracked test files, 17 die outright (the whole
`tests/recursive/` walk, `tests/scale/`, the dead `tests/fixtures/capability_seed/`,
the root/generated Ruff-parity test, and the template self-host parity test), 49
survive only after rewrite (the guard-rule suites read their policy by rendering
`template/architecture.toml.jinja` in a `tmp_path`, and the shape fixtures are
installed by a token-substituting installer into a generated repository), 2 are
reusable as-is (`test_proof_guard.py`, `test_release.py`), and one
(`test_instantiate.py`, 1291 lines) is the single largest file whose surviving
half belongs to the One-shot Bootstrap capability. In `docs/`, only
`docs/research/cli-agent-readiness-integration.md` is written against the
parallel tree; `docs/agents/*.md` are already CONTEXT.md-centric and reusable,
and `docs/vendored/` is orthogonal. `.agents/` and `.claude/` are entirely
project-agnostic third-party skills plus one hook setting: nothing there mentions
the meta-repository, `repoctl`, Copier, or the parallel tree, so nothing there
needs the maintainer-contract rewrite. The maintainer-contract wording that does
need rewriting lives in root `AGENTS.md`/`CLAUDE.md` (outside this scope), not in
`.agents/` or `docs/agents/`.

## Full coverage

Homogeneous fixture asset trees are given one row each, with their file count.
`docs/vendored/` is one row for 403 files, per the ticket.

| Path | Verdict | Reason |
|---|---|---|
| `tests/conftest.py` | REWRITE | Inserts `REPO_ROOT/scripts` **and** `REPO_ROOT/template` on `sys.path` and imports `instantiate` so every module can import the generator and the template guards (`tests/conftest.py:23-27`). Sets `sys.dont_write_bytecode` only to keep `__pycache__` out of `template/` (`tests/conftest.py:19-21`). With one tree, only the git-context isolation fixture survives (`tests/conftest.py:30-34`), and it survives only for the One-shot Bootstrap tests. |
| `tests/fixtures/capability_seed/` (10 files) | DELETE | Already dead. The only reference in the tree is a negative assertion that forbids referencing it (`tests/test_update_preservation.py:137-144`); the remaining mention is historical (`epics/epic-1.yaml:282`). The tree is a hand-seeded `.repo/capabilities/billing.toml` declaration plus its module skeleton — declarations do not exist in the target. |
| `tests/fixtures/mutation_catalog.json` | REWRITE | 14 SPEC-0001 mutations. Mutations 1-2 (planner path escapes), 3-5 (apply overwrite / stale digest / duplicate declaration) and 6-7 (derived compiler omits an active, includes a retired capability) are mutations of the plan/apply/derived-index machinery (`tests/mutations/test_mutation_catalog.py:21-40`) and die with it. Each entry also names `context: "generated_repository"` and evidence paths under `tests/repoctl/**`. Only the guard and proof-gate mutations survive. |
| `tests/fixtures/performance_budgets.json` | DELETE | A recorded budget for 100 `repoctl` capability commands (`status`, `capability_plan`, `capability_apply`, `generate`). No such commands exist in a Terminal Project. |
| `tests/fixtures/shapes/cli_capability/` (7 files) | REWRITE | The shape content (a capability-owned command boundary with an argparse-free catalog, a probe, a proof catalog, and a proof test) is genuine architecture evidence. The `.fixture` suffix and the `@MODULE@`/`@PROPERTY_ID@` token substitution exist only to inject the shape into a freshly rendered repository (`tests/recursive/shape_support.py:117-138`). Re-express as an ordinary checked-in example capability. |
| `tests/fixtures/shapes/composition/` (2 files) | REWRITE | Provider/consumer APIs that compose only through `src/<pkg>/_generated/composition.py` (`tests/recursive/test_shape_composition.py:32-44`). The composition-through-a-generated-index mechanism dies; the proof that a consumer never imports a provider's internals survives. |
| `tests/fixtures/shapes/external_integration/` (8 files) | REWRITE | Outbound-boundary shape, same injection mechanism. |
| `tests/fixtures/shapes/pure_library/` (5 files) | REWRITE | Pure proof-carrying function, same injection mechanism. |
| `tests/fixtures/shapes/stateful_workflow/` (8 files) | REWRITE | Stateful workflow shape, same injection mechanism. |
| `tests/mutations/test_mutation_catalog.py` | REWRITE | Audits the catalog against the 14 specification mutations and checks each names an existing deterministic killer (`tests/mutations/test_mutation_catalog.py:104-118`). The audit discipline survives; the mutation list must be re-derived once plan/apply/derived-index mutations no longer exist. |
| `tests/recursive/harness.py` | DELETE | The entire file is generation-and-`repoctl` process mechanics: `REPOCTL_PREFIX` (`:22`), `plan_and_apply` writing `.repo/plans/<cap>.json` (`:104-107`), `activate`/`retire` followed by `repoctl generate` (`:109-120`), and `_render_repository` calling `instantiate.generate` then `git init` (`:144-162`). |
| `tests/recursive/shape_support.py` | REWRITE | `product_hashes`/`assert_product_hashes` (`:70-97`) are the reusable proof that a pack operation does not touch user bytes. `runtime_capabilities` reads `src/<pkg>/_generated/active_capabilities.py` (`:100-114`) and dies with the generated index; `install_assets` (`:117-138`) and `run_detached` die with generation-into-a-temp-dir. |
| `tests/recursive/test_recursive_generation.py` | DELETE | The nineteen-step `template → N0 → N1 → N2` walk (`:1`, `:18-38`). Every step is a plan/apply/activate/retire/generate call or an assertion about a generated index. |
| `tests/recursive/test_shape_cli_capability.py` | REWRITE | Real proof (capability owns its command boundary, product bytes stay stable) is reached through `prepare_active_shape` and `repoctl capabilities` declaration reads. |
| `tests/recursive/test_shape_composition.py` | REWRITE | Proves a consumer reaches a provider only through `api` and that `CAP003` fires on a deep import (`:150-167`). That proof survives; the route through `.repo/capabilities/<cap>.toml` `factory = ""` rewriting (`:97-104`) and `_generated/composition` does not. |
| `tests/recursive/test_shape_external_integration.py` | REWRITE | Same shape/harness coupling. |
| `tests/recursive/test_shape_pure_library.py` | REWRITE | Proves the capability exposes only an analysed `api` and that CrossHair analyses the declared target (`:154-170`). Survives; the `repoctl capabilities` declaration read (`:141-153`) does not. |
| `tests/recursive/test_shape_stateful_workflow.py` | REWRITE | Same shape/harness coupling. |
| `tests/scale/performance_probe.py` | DELETE | Imports `repoctl.modules.repository_generation.api` directly (`:24-27`) and builds 100 capabilities through `capability plan`/`apply` (`:69-98`). |
| `tests/scale/test_capability_scale.py` | DELETE | Asserts `REPOCTL::INDEPENDENT-CAPABILITIES-COMMUTE` and records the budget file (`:23-35`). Commutativity of capability *commands* is meaningless when capabilities are filesystem-native and there are no commands. |
| `tests/test_cli_discipline.py` | REWRITE | Guardrail ARCH021-ARCH025 survives verbatim. Only the policy fixture is generation-shaped: it reads `template/architecture.toml.jinja` and does a literal `{{ package }}` replacement into a `tmp_path` (`:11`, `:15-21`). |
| `tests/test_crosshair_gate.py` | REWRITE | Black-box CrossHair budget/selection tests survive. Points at `template/scripts` (`:13`) and builds synthetic projects. |
| `tests/test_docs_guard.py` | REWRITE | DOC001-DOC007 all survive. The file imports `instantiate.generate` and renders `template/architecture.toml.jinja` (`:14-17`, `:27-39`), and `test_template_documentation_passes_the_guard` (`:176`) becomes "the Root Pack's own docs pass the guard". |
| `tests/test_hook_policy.py` | REWRITE | Pre-commit/pre-push/CI tiering survives. The file pins the recursive acceptance node id as the bounded pre-push job (`:9-12`). |
| `tests/test_instantiate.py` | MOVE-TO-BOOTSTRAP | 1291 lines, three distinct groups. (a) One-shot Bootstrap: `test_init_*` git/`gh` sequencing (`:801-949`), `test_refuses_to_overwrite_non_empty_directory` (`:712`), name validation (`:697`, `:705`). (b) DELETE: Copier answers/provenance (`:485`, `:529`), Jinja rendering and stray-suffix scans (`:951-1021`), delta-or-identical toggles (`:587-673`), worktree/dirty-tag generation (`:1022-1197`), `_exclude` single-source (`:1198`). (c) KEEP as ordinary Root Pack self-checks: architecture guard passes (`:1229`), docs guard passes (`:1248`), module ceiling is 650 (`:1242`), gate/doctor/justfile shape (`:261-463`), removed-vocabulary scan (`:1206`). `test_generated_n0_control_plane_executes` (`:1277`) dies with `repoctl`. |
| `tests/test_none_discipline.py` | REWRITE | ARCH016-ARCH018 survive verbatim; only the `template/architecture.toml.jinja` policy fixture is generation-shaped (`:19`, `:22-28`). |
| `tests/test_ownership_zones.py` | REWRITE | The core guardrail — the pack never writes a user-owned file — survives and is central. It is written as "no `template/` source renders into a PRODUCT root" using a Jinja `StrictUndefined` path renderer (`:14-32`, `:62-72`, `:96-112`), and asserts the generated tree has no example modules, no retired properties, and exactly one `repoctl/modules/*` control root (`:115-176`). |
| `tests/test_path_discipline.py` | REWRITE | ARCH019-ARCH020 survive verbatim; same `.jinja` policy fixture (`:19`, `:22-28`). |
| `tests/test_pin_coherence.py` | REWRITE | Pin coherence by tracked-tree scan is a good mechanism and survives (`:19-58`). `test_copier_pin_is_coherent` (`:60`) dies with Copier; the uv/prek/ruff/icontract/session-profiler pins stay. |
| `tests/test_proof_guard.py` | KEEP (Pack-owned Surface) | 1127 lines of fault injection against the closed proof contract, built from inline synthetic projects only (`:1`, `:14-25`). The word `repoctl` appears purely as a foundation-zone path token (`:25`, `:230-252`) and is a rename, not a rewrite. |
| `tests/test_release.py` | KEEP (Pack-owned Surface) | Copies `justfile` and `scripts/release.py` into a scratch git repository and proves the release command refuses a version missing from the changelog (`:12-33`). No generation, no template. |
| `tests/test_review_discipline.py` | REWRITE | ARCH026-ARCH031 survive verbatim; same `.jinja` policy fixture (`:11`, `:200-207`). |
| `tests/test_root_ruff_policy.py` | DELETE | Its whole purpose is that "the pack root and generated repositories share one Ruff policy" (`:1`, `:27-33`). With one self-hosting tree there is one policy and nothing to compare. |
| `tests/test_selfhost_validator.py` | DELETE | Loads `template/tests/repoctl/test_capability_contract.py` by file path (`:8-23`) to prove template *system* and *product* code execute identical rules and that there is no `repoctl` rule bypass (`:26-59`). The property becomes structurally true once one tree exists. |
| `tests/test_update_preservation.py` | REWRITE | "A real Copier update must never rewrite seeded product bytes" (`:1`). It imports `copier.run_copy`/`run_update` (`:16`), tags synthetic foundation versions (`:26-30`), and hashes seeded product files. The proof is the single most important survivor, restated as: a **Pack Update** replaces only **Pack-owned Surface** files and never touches **User-owned Surface** bytes. `test_update_scenario_no_longer_references_the_hand_seeded_fixture` (`:137`) is scaffolding and dies. |
| `docs/agents/domain.md` | KEEP (Pack-owned Surface) | Already written against `CONTEXT.md` and `docs/adr/`; no mention of `template/`, Copier, or generation. |
| `docs/agents/issue-tracker.md` | KEEP (Pack-owned Surface) | Pure `gh` conventions; repository-shape agnostic. |
| `docs/agents/triage-labels.md` | KEEP (Pack-owned Surface) | Label table only. |
| `docs/research/cli-agent-readiness-integration.md` | REWRITE | Every code citation is a `template/**.jinja` path (`:26-40`), and the note reasons about "the generated project" and "the template". The design conclusion survives; every path and every noun must be restated for one tree. |
| `docs/vendored/` (403 files) | KEEP (Pack-owned Surface) | Pinned, read-only, orthogonal to the change. `vendor-docs check` already guards it. No file in the tree references `template/`, `repoctl`, or Copier. |
| `.agents/skills/**` (84 tracked files + `thermo-nuclear-code-quality-review/SKILL.md`, untracked) | KEEP (Pack-owned Surface) | Project-agnostic third-party skills. A marker grep over the whole tree hits only generic senses of `plan`, `lifecycle`, and `template` (`.agents/skills/wizard/template.sh`, `.agents/skills/epic-worker/SKILL.md`, `.agents/skills/orchestrate-epic/runtime/*.py`). Nothing describes the meta-repository, `repoctl`, Copier, or the parallel tree. |
| `.agents/skills/setup-matt-pocock-skills/{domain,issue-tracker-*,triage-labels}.md` | KEEP (Pack-owned Surface) | The upstream sources of `docs/agents/*.md`; same verdict as their outputs. |
| `.claude/skills/**` (41 entries) | KEEP (Pack-owned Surface) | Symlinks into `.agents/skills/`; no content of their own. |
| `.claude/settings.json` | KEEP (Pack-owned Surface) | One `PostToolUse` hook running `python3 -B scripts/reminder_comment_hook.py`. The script is a root-owned guard that survives unchanged. |

Verdict counts (files): DELETE 17, REWRITE 50 (49 in `tests/`, 1 in `docs/`),
KEEP 2 in `tests/` + 3 in `docs/agents/` + `docs/vendored/` (403) + the whole
`.agents/`/`.claude/` trees, MOVE-TO-BOOTSTRAP 1.

## 1. `tests/recursive/` and `tests/fixtures/`

### What the recursive walk proves

`tests/recursive/test_recursive_generation.py` runs one nineteen-step scenario
(`:18-38`) and asserts the exact step sequence, the final runtime index, the
number of `capability plan`/`apply` invocations, and that every command written
between the `capability-workflow` markers in the generated `AGENTS.md` was
actually executed (`:189-210`). Underneath, it proves five distinct things:

1. **A freshly created capability contains no invented business logic.** Enforced
   by `assert_no_invented_business_logic` (`tests/recursive/harness.py:129-141`)
   against `NotImplementedError`, placeholder aggregate classes, and `assert True`;
   the check is itself proven load-bearing (`test_recursive_generation.py:232-241`).
2. **Adding, activating, or retiring one capability never changes another
   capability's bytes.** Three `assert_product_hashes` calls
   (`harness.py:246`, `:250`, `:256`).
3. **The documented workflow is the executed workflow.** Documentation commands
   are replayed against the recorded invocation list (`test_recursive_generation.py:49-66`,
   `:208-210`).
4. **The gate is green before and after the whole scenario** (`harness.py:238`, `:264`).
5. **The harness cannot cheat.** No direct `write_text`/`mkdir` primitive exists
   in the walk; product writes go through the single `ShapeFixture` seam
   (`test_recursive_generation.py:213-225`).

Proofs 1, 3, 4 and 5 die: they are properties of a generator that creates
capability skeletons and of a `repoctl` command vocabulary. Proof 2 survives, but
its subject changes: it is no longer "one capability's commands do not disturb
another capability", it is "a **Pack Update** does not disturb any **User-owned
Surface**" — already covered by `tests/test_update_preservation.py` and better
placed there.

Re-expression against a single tree: delete `tests/recursive/` entirely, keep
`product_hashes`/`assert_product_hashes` (`shape_support.py:70-97`) as a small
helper used by the Pack Update test, and keep the "no invented business logic"
regex set only if the One-shot Bootstrap still writes any skeleton at all — if
Terminal Projection copies whole files and substitutes only identity fields, it
does not, and the check goes too.

### What the shape fixtures prove

The five shapes (pure library, stateful workflow, external integration, CLI
capability, composition) each prove that a real, proof-carrying capability of that
shape passes the full gate, exposes only `api`, and is reachable from outside only
through `api`. `tests/recursive/test_shape_pure_library.py:118-170` is
representative: no stray application/adapter modules, empty inbound/outbound
boundaries in the declaration, exactly one external import
(`<pkg>.modules.alpha.api`), and CrossHair naming the property/target pair.

Those proofs matter more in the target model, not less: they are the only evidence
that the architecture rules admit real work. They are currently entangled with
generation in three ways — the shape lives in a `.fixture` file with `@MODULE@`
tokens, it is installed into a temp-dir repository, and the boundary assertion is
read out of a `repoctl capabilities` JSON declaration.

Re-expression against a single tree: check each shape in as an ordinary example
**Product Capability** inside the Root Pack (real files, no `.fixture` suffix, no
token substitution), and replace the declaration read with a direct static
assertion from `scripts/capability_validator` over the capability root. That
converts five slow subprocess acceptance tests into five ordinary in-tree tests
that the Root Pack's own gate already runs. Terminal Projection then decides
whether the example capabilities ship (User-owned Surface, likely removed) or not.

`tests/fixtures/capability_seed/` is already dead and can be deleted today.
`tests/fixtures/performance_budgets.json` measures `repoctl` commands and dies.
`tests/fixtures/mutation_catalog.json` needs re-derivation, not deletion.

## 2. Root test files, one by one

| File | Guardrail | Survives? |
|---|---|---|
| `test_cli_discipline.py` | ARCH021-ARCH025: no prompts in production paths, no uncontrolled process exit, no CLI-framework leakage, no literal or dynamic command registration, every catalog entry declares a primary input. | Yes, unchanged. Only the policy fixture changes. |
| `test_crosshair_gate.py` | Symbolic analysis is bounded, selects only declared symbolic targets, fails on an unrefuted canary, and names the owning property in a counterexample. | Yes. Path to `template/scripts` changes. |
| `test_docs_guard.py` | DOC001-DOC007: no broken path or link, ADR markers resolve, ADR naming/heading/front matter/numbering, every document registered in the map. | Yes. `test_template_documentation_passes_the_guard` becomes a self-check. |
| `test_hook_policy.py` | Pre-commit is fast, pre-push is bounded, CI is comprehensive; the hooks recipe provisions a durable prek. | Yes. The bounded pre-push job must name a different test than the recursive walk. |
| `test_instantiate.py` | Generation correctness, `init` ordering, Jinja completeness, artifact exclusion, plus several generated-repository gate self-checks. | Split: bootstrap ordering moves to the One-shot Bootstrap capability; Jinja/Copier/delta tests die; gate self-checks become ordinary Root Pack tests. |
| `test_none_discipline.py` | ARCH016-ARCH018: no `None`-defaulted collections, no optional domain fields, no optional domain returns. | Yes, unchanged. |
| `test_ownership_zones.py` | The pack never writes a user-owned file; the shipped tree carries no example modules, no retired core properties, no relaxed limits. | Yes, and it is the load-bearing survivor. Must be restated as **Terminal Projection** / **Pack Update** vs **User-owned Surface**. |
| `test_path_discipline.py` | ARCH019-ARCH020: path-shaped values are `Path`-typed. | Yes, unchanged. |
| `test_pin_coherence.py` | Every multi-location toolchain pin agrees, discovered by scanning the tracked tree. | Yes, minus the Copier pin. |
| `test_proof_guard.py` | The closed proof contract: property/oracle/target/evidence/canary chain, no self-judging oracle, no effectful oracle, exemption expiry. | Yes, as-is. |
| `test_release.py` | The release command refuses a version absent from the changelog. | Yes, as-is. |
| `test_review_discipline.py` | ARCH026-ARCH031: no mutable module state, no duplicate in-repository models, tokenized path values, no bare-primitive domain aliases, marked overrides, no reminder comments. | Yes, unchanged. |
| `test_root_ruff_policy.py` | Root and generated repositories share one Ruff policy. | No. Structurally true with one tree. |
| `test_selfhost_validator.py` | System code and product code execute identical rules; no `repoctl` rule bypass. | No as a test; the intent ("one rule set, no privileged zone") becomes an architecture property of the single tree and is worth one small assertion, not a file. |
| `test_update_preservation.py` | A pack update never rewrites user bytes. | Yes, and it becomes the primary Pack Update proof. |
| `conftest.py` | Import bootstrap and git-context isolation. | Partially: the git isolation fixture survives; the three-way `sys.path` insertion dies with the parallel tree. |

## 3. Shared machinery

- **`tests/conftest.py`** — the `sys.path` insertion of `REPO_ROOT`,
  `REPO_ROOT/scripts` and `REPO_ROOT/template` (`:23-25`) exists purely because
  guards live in a second tree. With one tree the guards are importable normally
  and this file shrinks to the `isolate_invoking_git_repository` fixture
  (`:30-34`), which only matters while the One-shot Bootstrap tests run `git`.
  `sys.dont_write_bytecode = True` (`:21`) exists to protect `template/` from
  `__pycache__` and can go.
- **`tests/recursive/harness.py`** — deleted in full. It is a `repoctl` process
  driver: `REPOCTL_PREFIX` (`:22`), `ACTIVATION_EVIDENCE` flags (`:23-29`),
  `plan_and_apply` writing `.repo/plans/<cap>.json` (`:104-107`), and
  `_render_repository` calling `instantiate.generate` (`:145`).
- **`tests/recursive/shape_support.py`** — only the hashing pair survives
  (`:70-97`). `runtime_capabilities` parses the generated index
  `src/<pkg>/_generated/active_capabilities.py` (`:100-114`); `select_capability`
  parses a `repoctl` declaration response (`:55-67`); `install_assets` performs
  the token substitution (`:117-138`). All three die.
- **`tests/scale/`** — both files die. They exist to prove that 100 *declarations*
  can be planned and applied within a time budget and that independent capability
  *commands* commute (`test_capability_scale.py:23`,
  `performance_probe.py:24-27`). A Terminal Project has no commands and no
  declarations, so nothing is being measured. If a scale concern survives at all,
  it is "the gate stays fast as capability count grows", which is a gate-timing
  test, not a control-plane benchmark.
- **`tests/mutations/`** — the *discipline* (every claimed mutation must name an
  existing deterministic killer, `test_mutation_catalog.py:118`) is valuable and
  survives. The catalog contents must be re-derived: 7 of the 14 entries mutate
  the planner, the apply step, or the derived compiler
  (`test_mutation_catalog.py:21-40`), and every entry's `evidence` field points
  into `tests/repoctl/**` or `verification/repoctl/**`.

## 4. Agent-facing instructions

`docs/agents/domain.md`, `docs/agents/issue-tracker.md`, and
`docs/agents/triage-labels.md` are clean. `domain.md` already routes agents to
`CONTEXT.md` and `docs/adr/` and says nothing about a template, a generated
repository, or two contracts. All three are **Pack-owned Surface** and project
unchanged into a Terminal Project.

`.agents/skills/` (84 tracked files plus one untracked skill) and `.claude/skills/`
(symlinks) are third-party, project-agnostic skills — TDD, code review,
domain modeling, epic orchestration, writing skills. A marker grep across both
trees returns only generic uses of `plan`, `lifecycle`, and the English word
`template`. `.claude/settings.json` wires one `PostToolUse` hook to
`scripts/reminder_comment_hook.py`, which is a root-owned guard that survives.

**Nothing in this scope carries the meta-repository maintainer contract.** The
"two contracts, do not confuse them" framing, the `template/` sources-of-truth
table, "fix the canonical source ... never by patching a generated copy", and the
`just validate` requirement all live in root `AGENTS.md` and root `CLAUDE.md`,
which are outside this inventory. The rewrite of that contract for a single
self-hosting tree therefore has no dependency on `docs/agents/` or `.agents/`.

## 5. Commands, paths, and workflows that will not exist

| Statement | Where | Why it dies |
|---|---|---|
| `just validate` generating a throwaway repository in a temp dir | referenced indirectly by every generation test; the recursive node id is pinned in `tests/test_hook_policy.py:9-12` | Nothing to generate; validation becomes the Root Pack's own gate. |
| `python-repo init <name>` with `git init` → `just bootstrap` → commit → `gh repo create` | `tests/test_instantiate.py:801-949` | Survives only as the One-shot Bootstrap capability, removed by Terminal Projection. |
| `uv run python -m repoctl capability plan/apply/activate/retire` and `repoctl generate` | `tests/recursive/harness.py:104-120`, all five shape tests, `tests/scale/performance_probe.py:54-98` | No `repoctl` in a Terminal Project. |
| `.repo/plans/<capability>.json` and `.repo/capabilities/<capability>.toml` | `tests/recursive/harness.py:105`, `tests/recursive/test_shape_composition.py:98`, `tests/fixtures/capability_seed/.repo/capabilities/billing.toml` | Product Capabilities have no declaration file and no lifecycle record. |
| `src/<pkg>/_generated/active_capabilities.py`, `src/<pkg>/_generated/composition.py` | `tests/recursive/shape_support.py:102`, `tests/recursive/test_shape_composition.py:37` | No generated capability indexes. |
| `template/architecture.toml.jinja` read and `{{ package }}`-substituted | `tests/test_cli_discipline.py:15-21`, `test_none_discipline.py:22-28`, `test_path_discipline.py:22-28`, `test_review_discipline.py:200-207`, `test_docs_guard.py:27-39`, `test_ownership_zones.py:15` | One tree has a real `architecture.toml`; tests read it directly. |
| `template/scripts/**`, `template/tests/repoctl/test_capability_contract.py` | `tests/conftest.py:25`, `tests/test_crosshair_gate.py:13`, `tests/test_selfhost_validator.py:8` | No parallel tree. |
| `copier.yml`, `_exclude`, `.copier-answers.yml`, `run_copy`/`run_update` | `tests/test_instantiate.py:485`, `:1198`, `tests/test_update_preservation.py:16-23`, `tests/test_ownership_zones.py:21` | Copier is gone. |
| Every `template/**.jinja` citation in prose | `docs/research/cli-agent-readiness-integration.md:26-40` | Paths no longer exist. |

## Guardrail proofs that must survive

1. **A pack operation never rewrites a user-owned byte.** Today:
   `tests/test_update_preservation.py:290` hashes seeded product files across a
   Copier `run_update`. Re-express: build a Terminal Project from the Root Pack in
   a temp dir, edit files across every **User-owned Surface** root, run a **Pack
   Update** from a newer Root Pack, and assert SHA-256 equality of every
   user-owned file plus byte-equality of every replaced **Pack-owned Surface**
   file against the new Root Pack's copy. This replaces both
   `test_update_preservation.py` and the three `assert_product_hashes` calls in
   the recursive walk.
2. **The pack ships nothing into user-owned roots.** Today:
   `tests/test_ownership_zones.py:96-112` proves no `template/` source renders
   into a PRODUCT root, using positive probes to prove the detector is
   load-bearing (`:110-112`). Re-express: classify every Root Pack file with
   `scripts/ownership`, assert the **Pack-owned Surface** set and the
   **User-owned Surface** set are disjoint and cover the tree, and keep the
   planted probes so the classifier is proven to fire.
3. **Terminal Projection changes only project identity and removes only the
   One-shot Bootstrap.** New proof, replacing the delta-or-identical toggle tests
   (`tests/test_instantiate.py:587-673`). Re-express: project the Root Pack into a
   temp dir and assert the file-set delta is exactly the bootstrap files, and that
   every remaining file is byte-identical to the Root Pack's after substituting
   the closed identity-field set.
4. **Every architecture rule fires and stays silent correctly (ARCH016-ARCH031,
   DOC001-DOC007, the proof contract, the CrossHair gate).** Today: six suites
   plus `tests/test_proof_guard.py`. Re-express: identical bodies, with the policy
   fixture reading the Root Pack's real `architecture.toml` instead of rendering a
   `.jinja` file into `tmp_path`.
5. **Real capabilities of each shape pass the full gate and expose only `api`.**
   Today: five acceptance tests over a generated repository. Re-express: five
   example **Product Capabilities** checked into the Root Pack, verified by the
   Root Pack's own gate plus a static import-boundary assertion.
6. **The documented workflow is the executed workflow.** Today: the
   `capability-workflow` marker replay (`tests/recursive/test_recursive_generation.py:49-66`).
   Re-express: keep the marker block in the Root Pack's `AGENTS.md` and replay its
   commands as an ordinary in-tree test — but the commands become filesystem and
   gate commands, not `repoctl` commands.
7. **A claimed mutation always has a named deterministic killer.** Today:
   `tests/mutations/test_mutation_catalog.py:118`. Re-express unchanged, over a
   re-derived catalog.
8. **Multi-location toolchain pins agree.** Today: `tests/test_pin_coherence.py`.
   Re-express unchanged, minus the Copier pin.
9. **Hook tiering: pre-commit fast, pre-push bounded, CI comprehensive.** Today:
   `tests/test_hook_policy.py:26`. Re-express unchanged, with a new bounded
   pre-push job.
10. **The release command refuses an unrecorded version.** Today:
    `tests/test_release.py:12`. Reusable as-is.

## Vocabulary to retire

| Term in scope | CONTEXT.md replacement | Highest-traffic files |
|---|---|---|
| template / template tree / `template/` | Root Pack | `tests/test_ownership_zones.py` (14 uses of `TEMPLATE_ROOT`), `tests/test_selfhost_validator.py:8`, all four guard suites' policy fixtures, `tests/conftest.py:25`, `docs/research/cli-agent-readiness-integration.md` |
| generated repository / generated tree / generated copy | Terminal Project | `tests/test_instantiate.py` (test names throughout), `tests/test_root_ruff_policy.py:1`, `tests/fixtures/mutation_catalog.json` (`context: "generated_repository"`, all 14 entries), `tests/scale/test_capability_scale.py:1` |
| meta-repository | Root Pack | absent from this scope; lives in root `AGENTS.md` |
| N0 / N1 / N2 | Terminal Project | `tests/recursive/test_recursive_generation.py:1`, `tests/recursive/harness.py:147`, `tests/test_instantiate.py:497`, `:1277`, `tests/test_ownership_zones.py:140` |
| recursive generation / recursion | One-shot Bootstrap (and: it does not recur) | the whole `tests/recursive/` package name, `tests/test_hook_policy.py:9` |
| template rendering / Jinja / Copier | Terminal Projection | `tests/test_instantiate.py:951-1021`, `tests/test_update_preservation.py:16`, `tests/test_ownership_zones.py:5`, `tests/test_pin_coherence.py:60` |
| scaffold / scaffold update | Pack Update | `tests/test_instantiate.py:497`, `:509` |
| declaration / registered capability / `.repo/capabilities/*.toml` | Product Capability (no declaration exists) | `tests/recursive/test_shape_composition.py:98`, `tests/recursive/test_shape_pure_library.py:149`, `tests/fixtures/capability_seed/.repo/capabilities/billing.toml`, `tests/fixtures/mutation_catalog.json` |
| lifecycle state: draft / active / retired, plan / apply / activate / retire | (no replacement; the concept is removed) | `tests/recursive/harness.py:104-120`, `tests/test_instantiate.py:1298`, all five shape tests |
| generated index / derived runtime index / `_generated` | (no replacement; removed) | `tests/recursive/shape_support.py:100-114`, `tests/recursive/test_shape_composition.py:37-44` |
| PRODUCT / product zone (as an ownership label) | User-owned Surface | `tests/test_ownership_zones.py:96-112`, `tests/recursive/shape_support.py:70-97` |
| FOUNDATION / system zone | Pack-owned Surface | `tests/recursive/harness.py:210`, `tests/test_proof_guard.py:25` |
| `repoctl` | (no replacement; removed from Terminal Projects) | 18 files, led by `tests/test_instantiate.py` (47 uses) and `tests/fixtures/mutation_catalog.json` (24) |

Note: `tests/test_instantiate.py:1206`
(`test_root_and_template_markdown_contain_no_removed_product_vocabulary`) is an
existing enforcement mechanism for exactly this kind of vocabulary retirement. It
should be kept and re-pointed at the CONTEXT.md _Avoid_ list, so the retirement
above is machine-enforced rather than a one-time edit.

## Open questions / uncertainties

1. **Do the five shape fixtures ship in a Terminal Project?** If they become
   in-tree example Product Capabilities, they are **User-owned Surface** and a new
   user probably wants them deleted on day one. Alternative: keep them as Root
   Pack test data that Terminal Projection removes alongside the One-shot
   Bootstrap. Not decided here.
2. **Where does the "no invented business logic" check live** if nothing generates
   a capability skeleton? It may become a review rule rather than a test.
3. **What replaces the mutation catalog's 7 control-plane entries?** They may have
   no successor at all, which would shrink SPEC-0001's claimed coverage. Someone
   must decide whether that is acceptable or whether new mutations of the Pack
   Update path replace them.
4. **Does any scale/timing budget survive?** `tests/scale/` measures a control
   plane that disappears. A gate-runtime budget is a different guardrail and does
   not exist today.
5. **How is a Pack Update tested without a second tree?** The proof in item 1
   above needs *two* Root Pack versions. Whether that is two git tags of the same
   repository, or two checkouts, is an open mechanism question that determines how
   much of `tests/test_update_preservation.py:146-289` (tag/publish helpers)
   survives.
6. **`tests/test_selfhost_validator.py`'s intent.** "No privileged zone bypasses
   the rules" is worth keeping as an assertion somewhere; I could not determine
   from the tests alone whether the single tree still has a distinguished
   foundation zone (`tests/test_proof_guard.py:25` suggests it does) or whether
   ownership zones collapse to the Pack-owned/User-owned split.
7. **`epics/epic-1.yaml`** still describes the deleted `capability_seed` scenario
   (`:282`, `:286`). It is outside this scope but will read as stale.
