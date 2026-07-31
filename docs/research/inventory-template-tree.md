# Inventory: `template/` tree against the Root Pack target

**Scope:** all 157 tracked files under `template/`. Vocabulary follows `CONTEXT.md`.

## Summary

The `template/` tree is roughly half reusable guardrail and half recursion machinery.
Seventy-six of the 157 files (48%) exist only to declare, plan, apply, journal, activate,
retire, and index nested repositories: almost all of the `repoctl/` package (32 of 34 files),
`tests/repoctl/` (15 of 16), `verification/repoctl/` (7 of 9), `proof/repoctl/` (2 of 3),
`.repo/` (2), `src/{{ package }}/_generated/` (4), `src/{{ package }}/adapters/` (5),
`SPEC-0001.md`, and the Copier answers file. Their sole consumers are each other. What survives is the
guardrail layer that never mentions a capability declaration: the AST fitness functions
(`scripts/architecture_rules.py`, `none_discipline`, `path_discipline`, `override_discipline`,
`review_discipline`, part of `cli_discipline`), the proof-catalog closure engine
(`scripts/proof_*.py`, 18 modules), the documentation guard, the doctor, the quality gate, and
the toolchain policy in `pyproject.toml.jinja` / `prek.toml` / `.github/workflows/quality.yml.jinja`.
Three pieces of surviving machinery are entangled with the generator and need rewriting rather
than deleting: `scripts/ownership.py` imports its path classifier straight out of
`repoctl.modules.repository_generation.api` (`template/scripts/ownership.py:6`);
`scripts/capability_validator.py` hard-codes `repoctl/modules` as a capability parent
(`template/scripts/capability_validator.py:309`); and `architecture.toml.jinja` declares the
`DERIVED` and `DECLARATION` ownership zones that filesystem-native Product Capabilities remove
(`template/architecture.toml.jinja:54-59`). Jinja is nearly free of real conditionality: only
five variables exist (`project_name`, `package`, `agents_contract`, `workspace_member`,
`_copier_conf.answers_file`), 22 of the 39 `.jinja` files substitute nothing but `package` or
`project_name`, and 5 contain no Jinja at all.

Counts over all 157 files: **DELETE 76, KEEP 47, REWRITE 34.** No file is pure IDENTITY;
identity appears as two *values* (`project_name`, `package`) substituted inside REWRITE/KEEP
files and into two path components.

## Full-coverage table

| Path (under `template/`) | Verdict | Surface | Reason |
|---|---|---|---|
| `.github/PULL_REQUEST_TEMPLATE.md` | REWRITE | Pack-owned | Checklist is reusable, but the "CLI catalog changes" and `proof/policy.toml` rows assume the repoctl command catalog; ownership-zone wording assumes DERIVED/DECLARATION. |
| `.github/workflows/quality.yml.jinja` | KEEP | Pack-owned | Contains zero Jinja; mirrors `just check`. Rename to `quality.yml` verbatim. |
| `.gitignore` | KEEP | Pack-owned | Pure artifact list, no recursion vocabulary. |
| `.repo/capabilities/repository_generation.toml` | DELETE | — | Capability declaration file with `status = "draft"` and lifecycle fields; declarations are removed. |
| `.repo/repository.toml.jinja` | DELETE | — | Repository declaration + `source_glob = ".repo/capabilities/*.toml"` registry. |
| `.vscode/settings.json` | KEEP | Pack-owned | Editor exclusions only. |
| `README.md.jinja` | REWRITE | Pack-owned | Prerequisites, daily commands, proof and session sections survive; the "N0 baseline" (`README.md.jinja:37-52`) and "Repository control" (`:54-64`) sections die. |
| `architecture.toml.jinja` | REWRITE | Pack-owned | See sub-section 2. Limits, conventions, and domain purity survive; `DERIVED`/`DECLARATION` zones and the `repoctl`, `proof/repoctl`, `.repo` roots die. |
| `docs/README.md.jinja` | REWRITE | Pack-owned | Documentation map survives as a rule; the SPEC-0001 row and the `agents_contract` conditionals die. |
| `docs/adr/0000-template.md` | KEEP | Pack-owned | ADR form, no recursion content. |
| `docs/adr/0001-foundation-ports-and-reference-adapters.md` | REWRITE | Pack-owned | The decision "ship no product exemplar" survives; its N0/repoctl justification does not. |
| `docs/adr/0002-agent-native-cli-protocol.md` | DELETE | — | Records that repository control owns the shipped command surface. |
| `docs/adr/0003-agent-session-evidence.md` | KEEP | Pack-owned | Session-evidence format and privacy constraints; independent of recursion. |
| `docs/adr/0004-agent-input-retry-and-composition-contract.md` | DELETE | — | Records capability plans as inspectable control artifacts. |
| `docs/adr/0005-review-finding-checks.md` | KEEP | Pack-owned | Rationale for ARCH026–ARCH031. |
| `docs/adr/0006-proof-carrying-core.md` | REWRITE | Pack-owned | Proof-carrying core survives; "N0 has no product behavior to prove, but it must prove the control plane" does not. |
| `docs/adr/0007-ownership-zones-replace-the-example-application.md` | REWRITE | Pack-owned | Two-zone Pack-owned / User-owned split survives; the four-zone DERIVED/DECLARATION model dies. |
| `docs/architecture/EXCEPTIONS.md` | REWRITE | Pack-owned | Ledger form survives; both active entries name `tests/repoctl/` and ADR-0002/ADR-0007. |
| `docs/architecture/MIGRATION_CHECKLIST.md` | KEEP | Pack-owned | Strangler / branch-by-abstraction checklist, generator-free. |
| `docs/architecture/PATTERN_ADMISSION.md` | KEEP | Pack-owned | Pattern-admission form, generator-free. |
| `docs/architecture/PROVABILITY.md.jinja` | REWRITE | Pack-owned | Oracle independence, canary, and evidence-sequence rules survive; the "N0 proof surface" and `proof/repoctl/` references die. |
| `docs/architecture/README.md.jinja` | REWRITE | Pack-owned | The fitness-function list survives; "N0 boundaries" and the `repoctl`/`_generated` seams die. |
| `docs/architecture/SPEC-0001.md` | DELETE | — | 1475-line specification titled "Recursive Proof-Carrying Repository"; §16 normative properties of the repository generator, §17 self-hosting, §7 capability declaration, §8 lifecycle, §13 derived compiler. Superseded wholesale by `CONTEXT.md`. |
| `justfile.jinja` | REWRITE | Pack-owned | All recipes survive; `{% if not workspace_member %}` conditionals in `bootstrap` and `update` must resolve. |
| `proof/_generated/index.json` | DELETE | — | Generated capability index with `source_state_sha256`; produced by the repoctl compiler. |
| `proof/foundation.toml.jinja` | KEEP | Pack-owned | Empty foundation catalog stub; no Jinja in it. Becomes the Pack-owned catalog. |
| `proof/policy.toml.jinja` | REWRITE | Pack-owned | Discovery config survives; `[catalogs] foundation = [..., "repoctl"]` and the `foundation`/`product` zone names change with the ownership model. |
| `proof/repoctl/repository-generation-apply.toml` | DELETE | — | `REPOCTL::APPLY-IDEMPOTENT`, `STALE-PLAN-REJECTED`, `PRODUCT-BYTES-PRESERVED`, `INDEPENDENT-CAPABILITIES-COMMUTE`. |
| `proof/repoctl/repository-generation-lifecycle.toml` | DELETE | — | `REPOCTL::ACTIVATION-CLOSED`, `RETIREMENT-NON-DESTRUCTIVE`: lifecycle state laws. |
| `proof/repoctl/repository-generation.toml` | REWRITE | Pack-owned | `DERIVED-INDEX-EXACT` and `PLAN-DETERMINISTIC` die; `PLAN-PATH-CLOSED` (path normalization + sole-owner classification) survives, renamed and retargeted. |
| `pyproject.toml.jinja` | REWRITE | Pack-owned | Ruff/BasedPyright/pytest/coverage policy is the single largest reusable asset; `src`/`include` lists and per-file-ignores name `repoctl` and `verification/repoctl`, and the import-linter contract layers `_foundation` over `_generated`. |
| `repoctl/__init__.py` | DELETE | — | Repository control plane package root. |
| `repoctl/__main__.py` | DELETE | — | `python -m repoctl` entry point. |
| `repoctl/bootstrap.py.jinja` | DELETE | — | Composition root of the control-plane CLI. |
| `repoctl/modules/__init__.py` | DELETE | — | "System capabilities owned by the repository control plane." |
| `repoctl/modules/repository_generation/__init__.py` | DELETE | — | The nested repository generator capability. |
| `repoctl/modules/repository_generation/adapters/__init__.py` | DELETE | — | Generator boundary adapters. |
| `.../adapters/inbound/__init__.py` | DELETE | — | Generator inbound adapters. |
| `.../adapters/inbound/cli.py.jinja` | DELETE | — | 511-line argparse boundary for control queries and mutations. |
| `.../adapters/inbound/cli_catalog.py.jinja` | DELETE | — | Closed registration surface for control commands (a registry). |
| `.../adapters/inbound/cli_mutations.py.jinja` | DELETE | — | 638-line plan/apply/activate/retire/generate command surface. |
| `.../adapters/inbound/cli_outcomes.py.jinja` | DELETE | — | Structured lifecycle mutation outcomes. |
| `.../adapters/inbound/cli_plan_document.py.jinja` | DELETE | — | Decoding for saved capability-plan documents. |
| `.../adapters/inbound/cli_plan_output.py.jinja` | DELETE | — | Plan-mutation output formatting. |
| `.../adapters/outbound/__init__.py` | DELETE | — | Generator outbound adapters. |
| `.../adapters/outbound/declaration_decoder.py` | DELETE | — | Reads capability declaration TOML. |
| `.../adapters/outbound/local_repository.py` | DELETE | — | 446-line durable filesystem repository port; writes declarations, derived indexes, journal. |
| `.../adapters/outbound/memory_repository.py` | DELETE | — | In-memory twin of the same port. |
| `.../api.py` | DELETE | — | Public surface of the generator capability; also the accidental home of the path classifier re-exports (see REWRITE of `domain/ownership.py`). |
| `.../application/__init__.py` | DELETE | — | Effect orchestration for repository generation. |
| `.../application/commands.py` | DELETE | — | Outcomes for capability-plan application. |
| `.../application/compilation.py` | DELETE | — | Regenerates declaration-derived indexes. |
| `.../application/journal.py` | DELETE | — | Durable transaction journal for plan application. |
| `.../application/lifecycle.py` | DELETE | — | `activate` / `retire` lifecycle transitions. |
| `.../application/ports.py` | DELETE | — | Repository filesystem port for the generator. |
| `.../application/specifications.py` | DELETE | — | Oracles for apply/activation/retirement outcomes. |
| `.../application/use_cases.py` | DELETE | — | Stale-safe apply protocol. |
| `.../domain/__init__.py` | DELETE | — | Pure generator values. |
| `.../domain/decisions.py` | DELETE | — | `plan()`: the pure planning decision. |
| `.../domain/indexes.py` | DELETE | — | 437-line `compile_indexes`: declarations → generated capability indexes. |
| `.../domain/intents.py` | DELETE | — | Declared capability state (DRAFT/ACTIVE/RETIRED) and structural intent. |
| `.../domain/ownership.py` | REWRITE | Pack-owned | The pure path normalizer + sole-owner classifier is genuinely reusable and is the only guardrail-critical code in `repoctl/`. It must move out of the generator into `scripts/`; the `OwnershipZoneRoots` shape survives, the four-zone assumption does not. |
| `.../domain/plans.py` | DELETE | — | Content-addressed capability plans. |
| `.../domain/plans_planner.py` | DELETE | — | Structural planning from snapshot + intent. |
| `.../domain/specifications.py` | REWRITE | Pack-owned | `classified_path_is_closed` survives with the classifier; `derived_indexes_are_exact` and `plan_repetition_is_identical` die. |
| `scripts/__init__.py` | KEEP | Pack-owned | Package docstring only. |
| `scripts/agent_sessions.py` | KEEP | Pack-owned | Facade over the pinned private session profiler; recursion-free. |
| `scripts/architecture_guard.py` | REWRITE | Pack-owned | Orchestration survives verbatim; line 80 calls `validate_repository_capabilities(root, policy.package_root)`, whose discovery must become filesystem-native. |
| `scripts/architecture_policy.py` | KEEP | Pack-owned | Loads `architecture.toml` limits/conventions/domain; no declaration or lifecycle concept. |
| `scripts/architecture_rules.py` | REWRITE | Pack-owned | See sub-section 1. Every generic rule survives; the three `REPOSITORY_GENERATION_*` constants and the `repoctl` production root die. |
| `scripts/capability_validator.py` | REWRITE | Pack-owned | CAP001–CAP003 are exactly the Product Capability contract; discovery must stop hard-coding `repoctl/modules` and the FOUNDATION/PRODUCT ownership argument. |
| `scripts/cli_discipline.py` | REWRITE | Pack-owned | ARCH021–ARCH023 (no prompts, no uncontrolled exit, framework confined to `adapters/inbound/cli.py`) survive; ARCH024/ARCH025 police the closed command *catalog* registry and only survive if a Terminal Project still declares one. |
| `scripts/crosshair_gate.py` | KEEP | Pack-owned | Bounded symbolic analysis driven by the proof catalog; catalog-shape agnostic. |
| `scripts/docs_guard.py` | KEEP | Pack-owned | DOC001–DOC007 over `docs/README.md` and `docs/adr/`; no recursion coupling. |
| `scripts/doctor.py` | KEEP | Pack-owned | Hooks, working tree, branch sync, `gh` auth, `uv sync`, Python version probes. |
| `scripts/none_discipline.py` | KEEP | Pack-owned | ARCH016–ARCH018; generic. |
| `scripts/override_discipline.py` | KEEP | Pack-owned | ARCH030; generic. |
| `scripts/ownership.py` | REWRITE | Pack-owned | Thin adapter, but line 6 imports the classifier from `repoctl.modules.repository_generation.api`. The adapter survives once the classifier moves. |
| `scripts/ownership_guard.py` | REWRITE | Pack-owned | OWN001–OWN004 survive unchanged; `REQUIRED_ZONE_NAMES` at line 33 pins the four zones including `DERIVED` and `DECLARATION`. |
| `scripts/ownership_policy.py` | KEEP | Pack-owned | Generic zone-roots loader; zone names are data. |
| `scripts/path_discipline.py` | KEEP | Pack-owned | ARCH019/020/028; generic. |
| `scripts/proof_assertions.py` | KEEP | Pack-owned | Proof-helper discovery. |
| `scripts/proof_ast.py` | KEEP | Pack-owned | AST binding/call resolution. |
| `scripts/proof_catalog.py` | REWRITE | Pack-owned | Loader survives; `ALLOWED_OWNERSHIP_ZONES` reaches it from `proof_catalog_model`. |
| `scripts/proof_catalog_model.py` | REWRITE | Pack-owned | Models survive; `ALLOWED_OWNERSHIP_ZONES = {"foundation", "product"}` (line 13) must follow the new ownership names. |
| `scripts/proof_catalog_schema.py` | REWRITE | Pack-owned | Schema survives; `_validate_catalog_zones` requires exactly the two zone names. |
| `scripts/proof_discovery.py` | KEEP | Pack-owned | Discovery facade. |
| `scripts/proof_evidence_rules.py` | KEEP | Pack-owned | One broad proof per property, one canary per oracle. |
| `scripts/proof_guard.py` | KEEP | Pack-owned | Closes property → contract → evidence. |
| `scripts/proof_guard_model.py` | KEEP | Pack-owned | Violation/evidence models. |
| `scripts/proof_invocations.py` | KEEP | Pack-owned | Exact proof-target invocation analysis. |
| `scripts/proof_model.py` | KEEP | Pack-owned | Shared proof models. |
| `scripts/proof_oracle_rules.py` | KEEP | Pack-owned | Independent, pure, boolean oracles. |
| `scripts/proof_reexports.py` | KEEP | Pack-owned | Facade-call resolution. |
| `scripts/proof_sources.py` | KEEP | Pack-owned | Behavior/contract/oracle discovery. |
| `scripts/proof_stateful.py` | KEEP | Pack-owned | Hypothesis state-machine evidence discovery. |
| `scripts/proof_target_rules.py` | KEEP | Pack-owned | Catalog closure over public behaviors. |
| `scripts/proof_tests.py` | KEEP | Pack-owned | Canonical proof and canary discovery. |
| `scripts/quality_gate.py.jinja` | KEEP | Pack-owned | Contains **zero** Jinja; the 11-check gate is the pack's spine. Rename to `.py` verbatim. |
| `scripts/review_discipline.py` | KEEP | Pack-owned | ARCH026/027/029/031; generic. |
| `src/{{ package }}/__init__.py.jinja` | REWRITE | User-owned | One docstring: "N0 package boundary for foundation and derived indexes." Path is IDENTITY (`package`); content must lose N0 and DERIVED. |
| `src/{{ package }}/_foundation/__init__.py` | REWRITE | Pack-owned | "Template-maintained foundation namespace"; the namespace survives as Pack-owned Surface, the word "template" does not. |
| `src/{{ package }}/_generated/__init__.py` | DELETE | — | "Declaration-derived indexes; empty in N0." |
| `src/{{ package }}/_generated/active_capabilities.py` | DELETE | — | Generated capability index (`ACTIVE_CAPABILITIES`), banner + `source-state-sha256`. |
| `src/{{ package }}/_generated/cli_catalog.py` | DELETE | — | Generated CLI catalog index. |
| `src/{{ package }}/_generated/composition.py` | DELETE | — | Generated composition index. |
| `src/{{ package }}/adapters/__init__.py` | DELETE | — | "Compatibility adapters retained for repository control." |
| `src/{{ package }}/adapters/inbound/__init__.py` | DELETE | — | "Compatibility declarations shared with repository control." |
| `src/{{ package }}/adapters/inbound/cli_contract.py.jinja` | DELETE | — | Closed declaration types "required by the repository-control command catalog". |
| `src/{{ package }}/adapters/inbound/cli_outcomes.py.jinja` | DELETE | — | Shared outcome codes for that catalog. |
| `src/{{ package }}/adapters/inbound/cli_protocol.py.jinja` | DELETE | — | The retained control-CLI protocol shim. |
| `src/{{ package }}/py.typed` | KEEP | Pack-owned | Empty marker; path is IDENTITY-parameterized. |
| `tests/e2e/session_contract.py` | KEEP | Pack-owned | Session-bundle assertions. |
| `tests/e2e/test_real_agent_sessions.py` | KEEP | Pack-owned | Opt-in session-evidence e2e. |
| `tests/e2e/test_session_evidence.py` | KEEP | Pack-owned | Session tool composition. |
| `tests/foundation/test_cli_protocol.py.jinja` | DELETE | — | Covers only the compatibility protocol retained for repository control. |
| `tests/repoctl/contract/cli_process_cases.py` | DELETE | — | 426-line declarative process cases for the control CLI. |
| `tests/repoctl/contract/conftest.py` | DELETE | — | Fixture for isolated repository-port contract runs. |
| `tests/repoctl/contract/repository_port_contract.py` | DELETE | — | Reusable contract *for the generator's* filesystem port. |
| `tests/repoctl/contract/test_local_repository.py` | DELETE | — | Certifies the local repository adapter. |
| `tests/repoctl/contract/test_memory_repository.py` | DELETE | — | Certifies the memory repository adapter. |
| `tests/repoctl/contract/test_repoctl_cli_contract.py` | DELETE | — | Process evidence for every control command. |
| `tests/repoctl/contract/test_repository_port_contract.py` | DELETE | — | Surface-coverage check of the port contract. |
| `tests/repoctl/integration/generation_support.py` | DELETE | — | Declaration/output helpers for derived-index evidence. |
| `tests/repoctl/integration/test_cli_mutations.py.jinja` | DELETE | — | Plan/apply/activate/retire process evidence. |
| `tests/repoctl/integration/test_cli_queries.py.jinja` | DELETE | — | Control read-command process evidence. |
| `tests/repoctl/integration/test_generate.py` | DELETE | — | Derived-index regeneration integration evidence. |
| `tests/repoctl/test_capability_contract.py` | REWRITE | Pack-owned | Proves system and product capabilities run one validator rule set; the *one-rule-set* idea survives for filesystem-native Product Capabilities, the "system capability" half dies. |
| `tests/repoctl/test_draft_capsule.py` | DELETE | — | Asserts the draft generator capsule has a real empty capability shape. |
| `tests/repoctl/unit/test_derived_indexes.py` | DELETE | — | Pure compiler evidence for generated indexes. |
| `tests/repoctl/unit/test_journal.py` | DELETE | — | Transaction journal evidence. |
| `tests/repoctl/unit/test_plan_models.py` | DELETE | — | Plan value-object evidence. |
| `tests/unit/generated/test_empty_repository_state.py.jinja` | DELETE | — | Asserts the generated indexes are empty and their digests match. |
| `tests/unit/scripts/pytest.ini` | KEEP | Pack-owned | Local no-coverage config for script tests. |
| `tests/unit/scripts/test_capability_validator.py` | REWRITE | Pack-owned | Follows `capability_validator.py`: CAP rule tests survive, the FOUNDATION/`repoctl` fixtures do not. |
| `tests/unit/scripts/test_ownership.py` | REWRITE | Pack-owned | Classifier tests survive; zone names and `_generated` fixtures change. |
| `tests/unit/scripts/test_ownership_guard.py` | REWRITE | Pack-owned | OWN001–OWN004 tests survive; the four required zone names and N0 fixtures change. |
| `verification/conftest.py` | KEEP | Pack-owned | Hypothesis profiles (`fast`/`ci`/`deep`) and `--property-id` selection. |
| `verification/harness/assertions.py` | KEEP | Pack-owned | `assert_property` / `assert_falsifies` / `assert_rejected`. |
| `verification/harness/repository_model.py` | DELETE | — | Primitive reference model for *repository capability application*. |
| `verification/harness/stateful.py` | KEEP | Pack-owned | Typed access to the Hypothesis stateful runner. |
| `verification/harness/symbolic_canary.py.jinja` | KEEP | Pack-owned | Contains zero Jinja; the deliberately false contract CrossHair must refute. Rename verbatim. |
| `verification/repoctl/specifications.py` | DELETE | — | `canonical_states_match` for the commute law. |
| `verification/repoctl/test_apply_state_machine.py` | DELETE | — | Stale-safe journaled apply. |
| `verification/repoctl/test_derived_index_properties.py` | DELETE | — | Derived-index compiler properties. |
| `verification/repoctl/test_independent_capabilities_commute.py` | DELETE | — | Metamorphic capability-order law. |
| `verification/repoctl/test_lifecycle_state_machine.py` | DELETE | — | Activation/retirement state machine. |
| `verification/repoctl/test_path_closed_properties.py` | REWRITE | Pack-owned | The only surviving `verification/repoctl/` law: path classification closure; moves with the classifier. |
| `verification/repoctl/test_plan_deterministic_properties.py` | DELETE | — | Plan determinism properties. |
| `verification/repoctl/test_proof_policy.py` | KEEP | Pack-owned | Asserts `proof/policy.toml` declares discovery roots as data; independent of repoctl despite its location. |
| `verification/repoctl/test_repository_state_machine.py` | DELETE | — | Repository capability protocol state machine. |
| `verification/tests/test_repoctl_evidence.py` | DELETE | — | Re-collects the repoctl proofs into the daily proof path. |
| `{% if agents_contract != 'none' %}AGENTS.md{% endif %}.jinja` | REWRITE | Pack-owned | See sub-section 5. |
| `{% if agents_contract != 'none' %}CLAUDE.md{% endif %}` | REWRITE | Pack-owned | One line (`@AGENTS.md`); only the `agents_contract` path conditionality dies. |
| `{% if not workspace_member %}.python-version{% endif %}` | KEEP | Pack-owned | `3.14`; only the `workspace_member` path conditionality dies. |
| `{% if not workspace_member %}prek.toml{% endif %}` | KEEP | Pack-owned | Hook policy; the ruff/architecture-guard/proof-contract/full-gate hooks all survive. |
| `{{ _copier_conf.answers_file }}.jinja` | DELETE | — | Copier provenance (`_commit`, `_src_path`); Terminal Projection has no Copier answers file. |

Row count: 157 (76 DELETE, 47 KEEP, 34 REWRITE). The IDENTITY verdict applies to values rather
than whole files: `project_name` and `package` are the closed identity set (see sub-section 4).
The one row marked IDENTITY inside sub-section 2 is `[project] package` in
`architecture.toml.jinja`.

---

## 1. `template/scripts/`, function by function

### `quality_gate.py.jinja` (256 lines, **no Jinja**)

Every function is a reusable Terminal Project guardrail. Nothing in it mentions declarations,
lifecycle, or indexes.

| Function | Verdict | Note |
|---|---|---|
| `repository_root()` (`:30`) | KEEP | Resolves from `__file__`. |
| `repairs()` (`:35`) | KEEP | `ruff check --fix`, `ruff format`. |
| `checks()` (`:45-70`) | KEEP | The 11 gates: `uv lock --check`, ruff format/check, basedpyright, `scripts.ownership_guard`, `scripts.architecture_guard`, `scripts.docs_guard`, `scripts.proof_guard`, `scripts.crosshair_gate ci`, `lint-imports`, `pytest`. |
| `run()` (`:73`) | KEEP | Subprocess runner with missing-tool hint. |
| `inspect_prek_hooks()` (`:84`) | KEEP | Checks the pre-commit/pre-push prek shims in the shared git hooks dir. |
| `print_hook_repair_failure()` / `ensure_prek_hooks()` (`:133`,`:147`) | KEEP | Self-repairing hook install. |
| `tracked_python_files()` / `check_tracked_python_syntax()` (`:176`,`:194`) | KEEP | Compiles every tracked `.py` before running the gate. |
| `requested_checks()` / `main()` (`:222`,`:231`) | KEEP | `--fix` handling, fail-fast. |

**Verdict: KEEP whole file, Pack-owned Surface, rename to `quality_gate.py`.**

### `architecture_rules.py` (437 lines)

| Function / constant | Verdict | Note |
|---|---|---|
| `REPOSITORY_GENERATION_{DOMAIN,APPLICATION}_SCOPE` and the three import/effect root sets (`:19-68`) | DELETE | Named allow-lists for `repoctl/modules/repository_generation/{domain,application}` only. |
| `Violation`, `is_under`, `dotted_name`, `import_roots`, `decorator_call`, `truthy_keywords`, `node_length`, `violation` (`:71-135`) | KEEP | Shared primitives, imported by six other guard modules. |
| `check_suppressions` — ARCH008/009/010 (`:138`) | KEEP | Bans `type: ignore`; requires `ARCH-EXCEPTION: ADR-` on every pyright/ruff suppression. |
| `check_init_file` — ARCH014/015 (`:171`) | KEEP | No `__init__.py` under `tests/`; no empty `__init__.py` elsewhere. |
| `check_module_shape` — ARCH001/002 (`:204`) | KEEP | Forbidden module stems; module line ceilings. |
| `check_function` — ARCH003/004 (`:229`) | KEEP | Function line ceiling; synchronous domain. |
| `check_class` — ARCH005/006/007 (`:255`) | KEEP | Class ceiling; immutable domain modules must be `frozen/slots/kw_only` dataclasses. |
| `check_import` — ARCH011/013 (`:301`) | REWRITE | The `policy.forbidden_import_roots` branch survives; the `ambient_effect_scope == REPOSITORY_GENERATION_*` allow-list branches (`:311-317`) die. ARCH013 (no `from __future__ import annotations`) survives. |
| `check_call` — ARCH012 (`:346`) | REWRITE | `policy.forbidden_call_suffixes` survives; the `REPOSITORY_GENERATION_APPLICATION_EFFECT_ROOTS` branch (`:357`) dies. |
| `is_domain_source` (`:376`) | REWRITE | Scans `policy.package_root` **and** `policy.root / "repoctl"` (`:378`); the second production root dies. |
| `ambient_effect_scope` (`:385`) | REWRITE | Three of its four branches hard-code `repoctl/modules/repository_generation/{domain,application}` (`:387-394`). Only the `is_domain_source` branch survives. |
| `check_tree`, `check_source` (`:400`,`:417`) | KEEP | Single-parse dispatch. |
| `python_files` (`:430`) | REWRITE | Roots list includes `policy.root / "repoctl"` (`:432`). |

### `architecture_guard.py` (91 lines)

`suppressed`, `check_files`, and `main` are reusable orchestration. `main:80` calls
`validate_repository_capabilities(root, policy.package_root)` — that call survives but its
discovery must change (below). **REWRITE, minimal.**

### `capability_validator.py` (386 lines) — the closest existing thing to a Product Capability guard

| Rule / function | Verdict | Note |
|---|---|---|
| CAP001 `required_structure_violations` (`:168`) | KEEP | Requires `api.py`, `domain/`, `application/`, `adapters/inbound/`, `adapters/outbound/`. This *is* the filesystem-native Product Capability shape. |
| CAP002 `layer_direction_violations` (`:185`) | KEEP | `domain ← application ← adapters`, `api`/`bootstrap` may reach anything, domain limited to stdlib + `icontract` (`:30-37`). |
| CAP003 `public_surface_violations` (`:226`) | KEEP | Outside code must import through `<capability>.api`. |
| `_capability` (`:253`) | REWRITE | Calls `classify_path` and rejects anything not `FOUNDATION`/`PRODUCT` (`:266-275`); ownership names change. |
| `discovered_capabilities` (`:304`) | REWRITE | Hard-codes `repoctl/modules → FOUNDATION` and `<package>/modules → PRODUCT` (`:309-310`). Only the second survives. |
| `REPOSITORY_PYTHON_ROOTS` (`:38`) | REWRITE | Contains `"repoctl"`. |
| `main` / `_arguments` (`:332`,`:356`) | REWRITE | `--ownership` choices are `FOUNDATION`/`PRODUCT`. |

### `ownership.py` / `ownership_policy.py` / `ownership_guard.py`

- `ownership.py` is a 74-line adapter whose entire import block comes from
  `repoctl.modules.repository_generation.api` (`template/scripts/ownership.py:6-23`). The
  *functions* (`normalized_relative_path`, `matching_zones`, `classify_path`) survive; the
  import must be repointed once the classifier leaves `repoctl/`. **REWRITE.**
- `ownership_policy.py` reads `[ownership.roots]` from `architecture.toml` and treats zone
  names as data (`:59-68`). **KEEP.**
- `ownership_guard.py`: OWN001 (overlapping roots), OWN002 (unclassified path), OWN003
  (ambiguous ownership), OWN004 (guard could not run) all survive. OWN005 pins
  `REQUIRED_ZONE_NAMES = {FOUNDATION, PRODUCT, DERIVED, DECLARATION}` (`:33`) — **REWRITE** to
  the Pack-owned / User-owned pair.

### The discipline modules

| Module | Rules | Verdict |
|---|---|---|
| `none_discipline.py` | ARCH016 mutable-collection default, ARCH017 optional domain field, ARCH018 optional domain return | KEEP |
| `path_discipline.py` | ARCH019 path-named parameter/return typed `Path`, ARCH020 path-named field, ARCH028 untokenized str used as a path | KEEP |
| `override_discipline.py` | ARCH030 explicit `@override` | KEEP |
| `review_discipline.py` | ARCH026, ARCH027, ARCH029, ARCH031 (ADR-0005 findings) | KEEP |
| `cli_discipline.py` | ARCH021 no prompt in unattended paths (`:58`), ARCH022 no uncontrolled exit / bare `SystemExit` (`:67`,`:232`), ARCH023 CLI framework confined to `adapters/inbound/cli.py` (`:36`) → KEEP. ARCH024 parser registration cannot be aliased (`:95-170`), ARCH025 catalog commands require ordinary arguments (`:153`) → these police the closed command *catalog*, an index-like registry. | REWRITE |

### The proof subsystem (18 modules)

`proof_guard.py` closes property → target → contract → oracle → Hypothesis proof → falsifying
canary → CrossHair target. None of it knows about capability declarations or lifecycle. It reads
only `proof/policy.toml` (`proof_catalog.py:148`) and the catalog files that policy points at.
**KEEP all 18**, except the three that carry `ALLOWED_OWNERSHIP_ZONES = {"foundation","product"}`
(`proof_catalog_model.py:13`, consumed at `proof_catalog_schema.py:114-123` and
`proof_catalog.py:50`) — **REWRITE for the new zone names only**.

### `docs_guard.py`, `doctor.py`, `crosshair_gate.py`, `agent_sessions.py`

All four are recursion-free. `docs_guard` enforces DOC001 (referenced path exists), DOC002
(`ARCH-EXCEPTION` names a real ADR), DOC003–DOC006 (ADR naming/heading/front matter/numbering),
DOC007 (document registered in the docs map). `doctor` probes hooks, working tree, branch sync,
`gh` auth, `uv sync`, Python version. `crosshair_gate` drives bounded symbolic analysis from the
catalog. **KEEP all four.**

---

## 2. `template/architecture.toml.jinja`, rule by rule

| Block | Verdict | Reason |
|---|---|---|
| `[project] package` (`:2`) | IDENTITY | `package`. |
| `[project] source_root = "src"`, `profile = "system"` (`:3-4`) | REWRITE | `source_root` survives; `profile = "system"` is a recursion-era distinction between the system (repoctl) and product profile. |
| `[ownership.roots] FOUNDATION` (`:7-46`) | REWRITE | Becomes the Pack-owned Surface list. Drop `.copier-answers.yml`, `proof/repoctl`, `repoctl`, `tests/repoctl`, `verification/repoctl`. Keep `.github`, `.gitignore`, `.python-version`, `.vscode`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `architecture.toml`, `docs/*`, `justfile`, `prek.toml`, `proof/foundation.toml`, `proof/policy.toml`, `pyproject.toml`, `scripts`, `src/<pkg>/_foundation`, `src/<pkg>/py.typed`, `tests/e2e`, `tests/unit`, `uv.lock`, `verification/conftest.py`, `verification/harness`, `verification/tests`. Drop `src/<pkg>/adapters` and `tests/foundation` with the compatibility CLI shim. |
| `[ownership.roots] PRODUCT` (`:47-53`) | KEEP | `src/<pkg>/modules`, `proof/modules`, `tests/modules`, `verification/modules`, `docs/product` are exactly the User-owned Surface of filesystem-native Product Capabilities. |
| `[ownership.roots] DERIVED` (`:54-58`) | DELETE | `src/<pkg>/_generated`, `proof/_generated`, `docs/architecture/generated` are generated capability indexes. |
| `[ownership.roots] DECLARATION = [".repo"]` (`:59`) | DELETE | The declaration registry root. |
| `[limits] max_module_lines 650 / max_test_module_lines 500 / max_function_lines 60 / max_class_lines 250` (`:61-65`) | KEEP | Pure size ceilings (ARCH002/003/005). |
| `[conventions] forbidden_module_stems`, `exception_marker` (`:67-69`) | KEEP | ARCH001 and the ADR-backed suppression marker. |
| `[domain] package = "domain"` (`:72`) | KEEP | Names the pure layer inside a capability. |
| `[domain] immutable_module_stems` (`:73`) | REWRITE | `entities, events, intents, plans, value_objects` — `intents` and `plans` are generator vocabulary; the mechanism survives, the default list should drop them. |
| `[domain] forbidden_import_roots` (`:74-96`) | KEEP | 22 effectful roots; ARCH011. |
| `[domain] forbidden_call_suffixes` (`:97-111`) | KEEP | Clocks, randomness, I/O, `print`; ARCH012. |

**Net:** the ownership *mechanism* (declared roots, no overlap, every path singly owned) is the
single most reusable guardrail in the tree. Only the four-zone taxonomy dies.

---

## 3. Declaration / lifecycle / registry / generated-index machinery — every producer and consumer

### Declaration files (`.repo/`)

- **Files:** `.repo/repository.toml.jinja` (schema, `project_name`, `package`,
  `[derived] source_glob = ".repo/capabilities/*.toml"`), `.repo/capabilities/repository_generation.toml`
  (`schema_version`, `name`, `python_module`, `status = "draft"`, `proof_catalog`,
  `[boundaries]`, `[activation]`).
- **Producers:** `repoctl/.../application/use_cases.py` (apply writes declarations),
  `repoctl/.../application/lifecycle.py` (activate/retire rewrite `status`),
  `repoctl/.../adapters/outbound/local_repository.py`.
- **Consumers:** `repoctl/.../adapters/outbound/declaration_decoder.py`,
  `repoctl/.../domain/indexes.py` (compiles them), `repoctl/.../domain/intents.py`,
  `architecture.toml.jinja` DECLARATION zone, `tests/repoctl/integration/*`,
  `verification/repoctl/test_repository_state_machine.py`, and the `AGENTS.md` capability
  lifecycle workflow.

### Lifecycle state

- **Producer:** `repoctl/modules/repository_generation/application/lifecycle.py` (`activate`,
  `retire`), fronted by `cli_mutations.py.jinja`.
- **Consumers:** `proof/repoctl/repository-generation-lifecycle.toml` (two laws),
  `verification/repoctl/test_lifecycle_state_machine.py`,
  `verification/repoctl/test_repository_state_machine.py`,
  `verification/tests/test_repoctl_evidence.py`,
  `tests/repoctl/contract/cli_process_cases.py`,
  `AGENTS.md` "Capability lifecycle workflow" block.

### Registries

- `.repo/repository.toml.jinja` `source_glob` (declaration registry).
- `repoctl/.../adapters/inbound/cli_catalog.py.jinja` — "Closed registration surface for
  repository-control commands", policed by ARCH024/ARCH025 in `scripts/cli_discipline.py`.
- `docs/README.md.jinja` "Registry" table — this one is a *documentation* registry and
  **survives** (DOC007).

### Generated capability indexes

- **Producers:** `repoctl/.../domain/indexes.py` (`compile_indexes`),
  `repoctl/.../application/compilation.py`, written by `local_repository.py` via
  `python -m repoctl generate`.
- **Artifacts:** `src/{{ package }}/_generated/{__init__,active_capabilities,cli_catalog,composition}.py`
  and `proof/_generated/index.json`, each carrying the banner
  `# Generated from repository declarations. DO NOT EDIT.` and a `source-state-sha256`.
- **Consumers:** `architecture.toml.jinja` DERIVED zone; the import-linter `layers` contract in
  `pyproject.toml.jinja:276-283`; `tests/unit/generated/test_empty_repository_state.py.jinja`
  (asserts they are empty and their digests match); `tests/repoctl/integration/test_generate.py`;
  `tests/repoctl/unit/test_derived_indexes.py`;
  `verification/repoctl/test_derived_index_properties.py`;
  `proof/repoctl/repository-generation.toml` (`REPOCTL::DERIVED-INDEX-EXACT`);
  `verification/harness/repository_model.py`; README, AGENTS.md, and
  `docs/architecture/README.md.jinja`.

### Proof catalogs under `proof/repoctl/`

Three catalogs, six properties. Five are generator laws. **One survives:**
`REPOCTL::PLAN-PATH-CLOSED` (every classified path is repository-relative and singly owned),
targeting `repoctl...domain.ownership:classify_path` with oracle
`...domain.specifications:classified_path_is_closed` and evidence in
`verification/repoctl/test_path_closed_properties.py`.

### Plans

`.repo/plans/NAME.json` is never a tracked file, but is produced by
`cli_mutations.py.jinja`, encoded/decoded by `cli_plan_document.py.jinja` and
`cli_plan_output.py.jinja`, modeled by `domain/plans.py` + `domain/plans_planner.py`, decided by
`domain/decisions.py`, applied by `application/use_cases.py`, journaled by
`application/journal.py`, and documented in README (`:61-62`) and the AGENTS.md workflow block.
All of it dies.

---

## 4. Jinja: identity substitution vs. real conditional rendering

Only five variables exist across the whole tree (`copier.yml`): `project_name`, `package`,
`agents_contract`, `workspace_member`, `_copier_conf.answers_file`.

**Closed identity field set (IDENTITY):** `project_name` and `package`. Nothing else in
`template/` is project identity.

### (a) Zero Jinja — already verbatim, only the `.jinja` suffix must go (5 files)

`.github/workflows/quality.yml.jinja` (its `${{ }}` is GitHub Actions syntax, not Jinja),
`proof/foundation.toml.jinja`, `scripts/quality_gate.py.jinja`,
`verification/harness/symbolic_canary.py.jinja`,
`repoctl/.../cli_plan_document.py.jinja` (deleted anyway).

### (b) Identity substitution only — become verbatim once `package`/`project_name` are fixed strings (22 files)

`{{ package }}` only: `architecture.toml.jinja`, `docs/architecture/PROVABILITY.md.jinja`,
`docs/architecture/README.md.jinja`, `proof/policy.toml.jinja`,
`repoctl/bootstrap.py.jinja`, `repoctl/.../cli.py.jinja`, `cli_catalog.py.jinja`,
`cli_mutations.py.jinja`, `cli_outcomes.py.jinja`, `cli_plan_output.py.jinja`,
`src/{{ package }}/adapters/inbound/cli_contract.py.jinja`, `cli_protocol.py.jinja`,
`tests/foundation/test_cli_protocol.py.jinja`,
`tests/repoctl/integration/test_cli_mutations.py.jinja`, `test_cli_queries.py.jinja`,
`tests/unit/generated/test_empty_repository_state.py.jinja`.

`{{ project_name }}` and/or `{{ package }}`: `.repo/repository.toml.jinja`.

Templated *paths* carrying `{{ package }}`: `src/{{ package }}/__init__.py.jinja`,
`.../adapters/inbound/cli_contract.py.jinja`, `cli_outcomes.py.jinja`, `cli_protocol.py.jinja`
(plus the non-`.jinja` files under `src/{{ package }}/`). The directory name stays
identity-substituted; nothing else about them needs rendering.

Note `src/{{ package }}/adapters/inbound/cli_outcomes.py.jinja` and
`src/{{ package }}/__init__.py.jinja` contain no Jinja in their *content* — only their path does.

### (c) Real conditional rendering today (5 files) — and why

| File | Condition | Why it exists |
|---|---|---|
| `justfile.jinja:13-15,41+` | `{% if not workspace_member %}` | Omits `uv sync --all-groups` and `prek install` when a uv workspace root owns them. |
| `pyproject.toml.jinja:13,31,33,38,40,271` | `{% if not workspace_member %}` | Omits `[dependency-groups]`, `[tool.uv] constraint-dependencies`, the whole Ruff/BasedPyright/pytest/coverage block. Import-linter contracts stay per-package. |
| `README.md.jinja:20,24,66,109` | `workspace_member` + `agents_contract` | Prek paragraph; two AGENTS.md cross-references. |
| `docs/README.md.jinja:27-29` and the trailing inline `{% if %}` | `agents_contract != 'none'` | AGENTS.md/CLAUDE.md registry rows. |
| `AGENTS.md.jinja:131-132` | `agents_contract == 'hooks-first'` | Adds check-loop step 6. |

Plus three templated *filenames* that are pure conditionality:
`{% if agents_contract != 'none' %}AGENTS.md{% endif %}.jinja`,
`{% if agents_contract != 'none' %}CLAUDE.md{% endif %}`,
`{% if not workspace_member %}prek.toml{% endif %}`,
`{% if not workspace_member %}.python-version{% endif %}`.

**Conclusion:** `agents_contract` and `workspace_member` are *not* project-identity fields. If
Terminal Projection substitutes only a closed identity set, both must be resolved to a fixed
choice at the Root Pack (the pack decides; the projection does not ask), which removes all
remaining conditional rendering and leaves `project_name`/`package` as pure string substitution.
`{{ _copier_conf.answers_file }}.jinja` is the only file that exists *because* Copier exists.

---

## 5. The conditional `AGENTS.md` template and `agents_contract`

**File:** `template/{% if agents_contract != 'none' %}AGENTS.md{% endif %}.jinja`, 163 lines.
Verdict **REWRITE**, Pack-owned Surface.

Sections that die outright:

- "N0 baseline" (`:15-27`) — N0, `repoctl.modules.repository_generation` as the sole shipped
  system capability, `src/{{ package }}/adapters/inbound/` compatibility declarations.
- "Repository control" (`:59-77`) — `python -m repoctl`, plan purity, saved control plans,
  apply/`already_applied`, activation evidence, retirement.
- "Capability lifecycle workflow" (`:79-113`) — the entire fenced block between
  `<!-- capability-workflow:start -->` and `<!-- capability-workflow:end -->`; 12 `repoctl`
  commands. This block is also the pack's recursive acceptance script, so its deletion removes
  the N0 → N1 → N2 walk's contract.
- "Before editing" item 2 (classify as FOUNDATION/PRODUCT/DERIVED/DECLARATION) and item 5
  ("use repository control … never invent product semantics in N0").
- "While editing" item 3 (repository-control boundary) and the DERIVED banner clause in item 4.
- "Proof-carrying behavior" first paragraph (`proof/repoctl/` as N0's active catalog).

Sections that survive nearly verbatim: the objective hierarchy (`:5-13`), "While editing" items
1/2/5, the check loop (`:115-132`, minus the hooks-first conditional), "Documentation and
decisions", "Type, state, and boundary discipline", and "Testing and review".

`agents_contract` has three values (`full`, `hooks-first`, `none`) and reaches four files:
the AGENTS.md filename, the CLAUDE.md filename, `README.md.jinja:66,109`, and
`docs/README.md.jinja:27-29`. `CLAUDE.md` is a one-line `@AGENTS.md` import. Under Terminal
Projection this must collapse to a single fixed contract — otherwise the projected surface is
not byte-identical to the Root Pack's.

---

## Reusable guardrail inventory

Each guardrail with where it is enforced today.

**Toolchain and process**

1. Eleven-stage quality gate, fail-fast, with `--fix` repairs — `scripts/quality_gate.py.jinja:45-70`.
2. Tracked-Python syntax pre-check before any gate runs — `scripts/quality_gate.py.jinja:194`.
3. Self-repairing prek pre-commit/pre-push hook install — `scripts/quality_gate.py.jinja:84-173`, `prek.toml`.
4. CI mirror of the gate — `.github/workflows/quality.yml.jinja`.
5. Deployment readiness probes (hooks, tree, branch sync, `gh` auth, `uv sync`, Python version) — `scripts/doctor.py:248`.
6. Lockfile freshness — `uv lock --check` gate + the `uv-lock` prek hook.
7. Ruff rule selection, per-file ignores, isort/tidy-imports policy — `pyproject.toml.jinja:45-195`.
8. BasedPyright `recommended` + `failOnWarnings` + 12 explicit report policies — `pyproject.toml.jinja:197-223`.
9. pytest strict config/markers, sockets disabled, 90% branch-coverage floor — `pyproject.toml.jinja:225-269`.
10. Import-linter layer contract — `pyproject.toml.jinja:271-283` (contract content must be rewritten; the mechanism survives).

**Ownership**

11. Single declared ownership map with no overlapping roots (OWN001) — `scripts/ownership_guard.py:59`.
12. Every tracked and untracked path has exactly one owner (OWN002/OWN003) — `scripts/ownership_guard.py:111`.
13. Pure, filesystem-free path normalization: absolute, `..`, empty segment, non-canonical separator, Unicode-normalization rejection — `repoctl/modules/repository_generation/domain/ownership.py`, surfaced via `scripts/ownership.py`.

**Architecture (AST fitness functions)**

14. ARCH001 no `utils`/`helpers`/`common`/`misc` — `architecture_rules.py:204`.
15. ARCH002/003/005 module, function, class line ceilings — `architecture_rules.py:204,229,255`.
16. ARCH004 synchronous domain — `architecture_rules.py:250`.
17. ARCH006/007 immutable domain messages are `frozen/slots/kw_only` dataclasses — `architecture_rules.py:255`.
18. ARCH008/009/010 no blanket `type: ignore`; every suppression carries `ARCH-EXCEPTION: ADR-` — `architecture_rules.py:138`.
19. ARCH011 domain must not import effectful roots — `architecture_rules.py:301`.
20. ARCH012 domain must not call clocks, randomness, I/O, or `print` — `architecture_rules.py:346`.
21. ARCH013 no `from __future__ import annotations` on 3.14 — `architecture_rules.py:335`.
22. ARCH014/015 test packages are PEP 420; no empty `__init__.py` — `architecture_rules.py:171`.
23. ARCH016–018 None discipline — `scripts/none_discipline.py:81,102,120`.
24. ARCH019/020/028 path discipline (`pathlib.Path`, never `str`) — `scripts/path_discipline.py:90,122,215`.
25. ARCH021/022/023 unattended CLI discipline — `scripts/cli_discipline.py:58,67,36,232`.
26. ARCH026/027/029/031 recurring review findings — `scripts/review_discipline.py:74,110,170,188` (ADR-0005).
27. ARCH030 explicit `@override` — `scripts/override_discipline.py:76`.
28. Central ADR-marker suppression for ARCH016–031 only — `scripts/architecture_guard.py:31,34`.

**Capability structure** (this is the Product Capability contract)

29. CAP001 required vertical shape `api.py` + `domain/` + `application/` + `adapters/{inbound,outbound}/` — `scripts/capability_validator.py:168`.
30. CAP002 layer direction `domain ← application ← adapters`; domain limited to stdlib + `icontract` — `scripts/capability_validator.py:185`.
31. CAP003 outside code imports only `<capability>.api` — `scripts/capability_validator.py:226`.

**Proof**

32. Closed property → target → `icontract` → oracle → Hypothesis proof → falsifying canary → CrossHair chain — `scripts/proof_guard.py`.
33. Catalog schema and cross-catalog uniqueness of property IDs — `scripts/proof_catalog.py:50-72`, `scripts/proof_catalog_schema.py`.
34. Oracles must be independent, pure, boolean — `scripts/proof_oracle_rules.py`.
35. One broad proof and one canary per property — `scripts/proof_evidence_rules.py`.
36. Exact-target invocation matching (no proof by proxy) — `scripts/proof_invocations.py`.
37. Reachable-only stateful evidence — `scripts/proof_stateful.py`.
38. Symbolic silence is not evidence: the deliberately false canary must be refuted — `scripts/crosshair_gate.py` + `verification/harness/symbolic_canary.py.jinja`.
39. Bounded Hypothesis profiles `fast`/`ci`/`deep` and `--property-id` selection — `verification/conftest.py`.
40. Property-ID-carrying assertion helpers — `verification/harness/assertions.py`.
41. Discovery roots declared as data, not code — `verification/repoctl/test_proof_policy.py`.

**Documentation**

42. DOC001 every cited path exists — `scripts/docs_guard.py:102`.
43. DOC002 every `ARCH-EXCEPTION` names a real ADR — `scripts/docs_guard.py:186`.
44. DOC003–DOC006 ADR naming, heading, front matter, numbering — `scripts/docs_guard.py:118-178`.
45. DOC007 no unregistered document — `scripts/docs_guard.py:213`.
46. Exception ledger, pattern-admission form, migration checklist, PR template — `docs/architecture/*`, `.github/PULL_REQUEST_TEMPLATE.md`.

**Agent evidence**

47. Opt-in, credential-free, socket-disabled session-evidence capture — `scripts/agent_sessions.py`, `tests/e2e/*`, ADR-0003.

---

## Vocabulary to retire

Terms found under `template/`, with the `CONTEXT.md` replacement.

| Term in `template/` | Where (examples) | `CONTEXT.md` replacement |
|---|---|---|
| N0 / N1 / N2 / N3 | `README.md.jinja:3,37`; `AGENTS.md.jinja:15`; `docs/architecture/README.md.jinja:3`; `PROVABILITY.md.jinja:3`; `SPEC-0001.md:32`; ADRs 0001/0002/0006/0007; `src/{{ package }}/__init__.py.jinja:1`; `src/{{ package }}/_generated/__init__.py:1` | **Terminal Project** |
| recursive generation / recursive repository / self-hosting | `SPEC-0001.md:1,§17`; `README.md.jinja`; `docs/README.md.jinja` (SPEC-0001 row); `AGENTS.md.jinja:86` | **One-shot Bootstrap** |
| template / template-maintained / scaffold update | `src/{{ package }}/_foundation/__init__.py:1`; `README.md.jinja:44`; ADR-0007; `SPEC-0001.md:§20` | **Root Pack**, **Pack-owned Surface**, **Pack Update** |
| generated repository | `scripts/quality_gate.py.jinja:31`; `scripts/ownership_policy.py:1`; `scripts/ownership_guard.py:153`; `pyproject.toml.jinja:8` (implied) | **Terminal Project** |
| repository control / control plane / `repoctl` | `repoctl/**`; `README.md.jinja:54`; `AGENTS.md.jinja:59`; ADR-0002 | *(no replacement — removed)* |
| capability declaration / declaration catalog / DECLARATION zone | `.repo/**`; `architecture.toml.jinja:59`; `AGENTS.md.jinja:31`; `declaration_decoder.py` | **Product Capability** (its owned code is its source of truth) |
| capability lifecycle / DRAFT / ACTIVE / RETIRED / activate / retire | `application/lifecycle.py`; `domain/intents.py`; `proof/repoctl/repository-generation-lifecycle.toml`; `AGENTS.md.jinja:79-113` | *(no replacement — removed)* |
| derived index / DERIVED zone / `_generated` | `src/{{ package }}/_generated/*`; `proof/_generated/index.json`; `architecture.toml.jinja:54` | *(no replacement — removed)* |
| capability plan / plan apply / already_applied / journal | `domain/plans*.py`; `application/{use_cases,journal}.py`; ADR-0004; `README.md.jinja:61` | *(no replacement — removed)* |
| system capability vs. product capability | `capability_validator.py:2,309`; `repoctl/modules/__init__.py:1`; `architecture.toml.jinja:4` (`profile = "system"`) | **Product Capability** (single kind) |
| registered capability / registration surface / CLI catalog | `cli_catalog.py.jinja:1`; `_generated/cli_catalog.py`; `cli_discipline.py` ARCH024/025 | **Product Capability** |
| FOUNDATION zone | `architecture.toml.jinja:7`; `ownership_guard.py:33`; `capability_validator.py:16` | **Pack-owned Surface** |
| PRODUCT zone | `architecture.toml.jinja:47` | **User-owned Surface** |
| Copier / `_commit` / `.copier-answers.yml` | `{{ _copier_conf.answers_file }}.jinja`; `architecture.toml.jinja:8`; `README.md.jinja:14` | **Terminal Projection** |
| child repository / nested repository / generator | `SPEC-0001.md` throughout; `docs/README.md.jinja` (SPEC-0001 row) | **Terminal Project** |

---

## Open questions / uncertainties

1. **Where does the pure path classifier live?** `repoctl/modules/repository_generation/domain/ownership.py`
   is the only guardrail-critical module inside the tree being deleted, and
   `scripts/ownership.py:6` imports it through the generator's `api.py`. Moving it into
   `scripts/` makes `scripts/` contain domain-pure code, which the current
   `capability_validator` layering rules do not describe. Its surviving proof
   (`REPOCTL::PLAN-PATH-CLOSED`) and evidence
   (`verification/repoctl/test_path_closed_properties.py`) must move with it.
2. **How many ownership zones remain?** `CONTEXT.md` names exactly two surfaces. Two zones
   simplify OWN005, but `proof_catalog_model.ALLOWED_OWNERSHIP_ZONES`, the proof `[catalogs]`
   layout, and `capability_validator`'s `--ownership` argument all encode the current names, so
   this decision ripples through six files.
3. **Does the Terminal Project keep a CLI at all?** ARCH021–ARCH025 and
   `src/{{ package }}/adapters/inbound/cli_*.py` exist for the control-plane CLI. If the
   Terminal Project ships no CLI by default, ARCH024/ARCH025 become dead rules and
   `cli_discipline.py` shrinks to three checks. If a Product Capability may declare a CLI, the
   catalog rules survive but need a non-generated catalog to police.
4. **What replaces the recursive acceptance walk?** The `<!-- capability-workflow -->` block in
   `AGENTS.md.jinja:87-112` is executed by the pack's N0 → N1 → N2 test. Deleting it removes the
   pack's only end-to-end proof that a projected repository is usable. A Root-Pack-era
   equivalent (project once, run `just check` in the result) is implied but not designed.
5. **`agents_contract` and `workspace_member`.** Neither is project identity. Fixing both at the
   Root Pack removes all conditional rendering, but `workspace_member = true` currently omits
   the entire Ruff/BasedPyright/pytest/coverage block from `pyproject.toml.jinja`. If uv-workspace
   membership must stay supported, it cannot be expressed by Terminal Projection as defined.
6. **`profile = "system"`** in `architecture.toml.jinja:4` is read nowhere in
   `scripts/architecture_policy.py`. It may already be dead configuration; I did not find a
   consumer.
7. **Import-linter contract content.** The only contract layers `_foundation` over `_generated`.
   With `_generated` gone, the Root Pack needs a new default contract or the `[tool.importlinter]`
   section becomes vacuous while `lint-imports` stays in the gate.
8. **`tests/foundation/` and `src/{{ package }}/adapters/`** are marked DELETE because their own
   docstrings say they exist only for repository control. If a Terminal Project is expected to
   ship a starting inbound adapter shape, these could be REWRITE instead — that is a product
   decision, not something the current code answers.
