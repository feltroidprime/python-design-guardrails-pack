# Root generation and packaging surface — inventory against the Root Pack target

**Summary.** The root scope is almost entirely two-tree machinery. Of the 17 tracked
paths in scope, only three survive essentially unchanged (`scripts/release.py`,
`.vscode/settings.json`, and the Ruff policy block inside `pyproject.toml`), one
survives as the seed of the One-shot Bootstrap capability (the git/bootstrap/commit/`gh`
pipeline in `instantiate.py`, lines 128-227 and 241-328), and everything else either
dies with Copier or must be rewritten because it describes a maintainer repository that
is *not itself* a project. The deepest structural finding is that the root today is
deliberately venv-less, lock-file-free, and gate-free: `justfile:8-10` provisions every
tool through `uv run --no-project --with`, `.gitignore:8-10` deletes any `uv.lock`, and
`pyproject.toml:204-208` excludes `template` from BasedPyright because "type-checking it
in place is meaningless". The root therefore runs **only** Ruff and pytest on itself; type
checking, coverage, architecture, ownership, docs, proof, and import-linter guards exist
only downstream, inside `template/`. In the target the Root Pack has the same contract as
a Terminal Project, so all of those guardrails must migrate onto the root itself, and the
root gains a real virtualenv and lockfile. The second finding is that `AGENTS.md`'s
central organizing idea — "Two contracts, do not confuse them" (`AGENTS.md:30-42`) —
disappears entirely: with one self-hosting tree there is exactly one contract.

## Verdicts

| Path | Verdict | Reason | Notes |
|---|---|---|---|
| `instantiate.py` | MOVE-TO-BOOTSTRAP | The Copier rendering core dies; the repository-preparation pipeline (git init, bootstrap, commit, `gh repo create`) is exactly the One-shot Bootstrap capability. | Sub-file breakdown below. Removed by Terminal Projection. The legacy positional `main()` (`instantiate.py:230-238`) is DELETE — it exists only because the pack's own tests and `validate_pack.py` depend on a network-free local form (`AGENTS.md:22-25`). |
| `copier.yml` | DELETE | Pure Copier engine configuration for a `_subdirectory` template tree. The target has no renderer, no question file, and no variant matrix. | Only `project_name` and `package` survive, as two of the closed set of project-identity fields, re-expressed as code inside the Bootstrap capability. `agents_contract` and `workspace_member` are variant switches and die — Terminal Projection substitutes identity fields only, and keeps every other surface byte-identical. |
| `pyproject.toml` (root) | REWRITE | Mixes a dying generator-packaging section with the surviving canonical Ruff policy. | Sub-file breakdown below. This file becomes the Root Pack's own project metadata: a real project with dev groups and a lockfile, not a generator wheel. |
| `justfile` (root) | REWRITE | `check`, `release`, and `hooks` survive; `validate`, `install`, and the recursion-scheduling in `test`/`test-fast` die. | Sub-file breakdown below. The target root justfile is the Terminal Project justfile (`bootstrap`, `check`, `prove`, `doctor`, `update`) plus the Bootstrap recipes. Pack-owned Surface. |
| `prek.toml` | REWRITE | Two-stage local-hook wiring is a good Pack-owned Surface file; its two hook bodies name recursion-shaped recipes. | `prek.toml:1-10` survives verbatim. `prek.toml:12-19` (`pack-fast` → `just test-fast`) and `prek.toml:21-31` (`pack-push` → `just test`, comment "one real N0 -> N1 -> N2 acceptance walk", "seven-minute warm-cache budget") are rewritten to the Terminal Project hook policy. The root currently has *no* `default_language_version.python`, unlike the generated `prek.toml` (see `VALIDATION.md:12-13`) — the merged file must adopt the downstream 3.14 pin. |
| `scripts/validate_pack.py` | REWRITE | ~40% is Copier/two-tree scaffolding that dies; ~60% is genuinely valuable fault-injection acceptance that must become normal Root Pack tests plus Bootstrap-capability acceptance. | Sub-file breakdown below. This is the single most valuable file to salvage carefully. |
| `scripts/release.py` | KEEP | Changelog-backed annotated tag with a clean-tree precondition. No Copier, no template, no recursion. | Pack-owned Surface. Only the two strings `"Template release {version}"` (`scripts/release.py:79`) and `"Created template release tag"` (`:82`) need retiring. `TAG_PATTERN` (`:11`) and the `LOCAL_GIT_ENVIRONMENT` scrubber (`:12-34`) survive as-is; note that scrubber is duplicated verbatim in `instantiate.py:31-53`. |
| `scripts/reminder_comment_hook.py` | REWRITE | The ARCH031 edit-time hook survives; its import path is bound to the two-tree layout. | Only `scripts/reminder_comment_hook.py:15` (`sys.path.insert(0, str(REPO_ROOT / "template"))`) dies. In the Root Pack, `scripts/review_discipline.py` is a first-party module at the root, so the import at `:17` becomes a plain import. Pack-owned Surface. Its wiring lives in `.claude/settings.json` (out of scope, but it invokes this file). |
| `.github/workflows/quality.yml` | REWRITE | The workflow shape (uv pin, `just`, one canonical gate) survives; its content is two-tree-specific. | `quality.yml:27-32` `fetch-depth: 0` + `fetch-tags: true` exists solely so update-roundtrip tests can clone the checkout and resolve the previous release tag — a Copier-update concern. `:44-45` `just validate` becomes the Terminal Project gate. `:24` `timeout-minutes: 45` reflects the recursive-walk budget and should shrink. `:35-39` (venv-less/lock-free comment, uv 0.12.0 pin) is REWRITE: the Root Pack has a lockfile. Pack-owned Surface. |
| `CHANGELOG.md` | REWRITE | The changelog *mechanism* survives (it is the contract `scripts/release.py:63-67` enforces); its framing and most entries are template/Copier history. | `CHANGELOG.md:1-10` DELETE — "Template changelog", "Generation from a release must pin that tag with Copier's `vcs_ref`", "`git describe` development identity". The `[Unreleased]` block mixes surviving guardrail history (Ruff curation `:33-46`, proof-carrying core `:47-64`, ARCH031 `:68-74`, `just check` hardening `:85-88`, `just doctor` `:89-92`) with dying entries (`:13-16` N0/generated indexes, `:17-21` `just scaffold-update` Copier workflow, `:22-28` the `precommit` Copier question, `:96-113` `workspace_member` Copier question). Becomes the Pack Update changelog. |
| `README.md` | REWRITE | Every sentence is written from the meta-repository standpoint. | `README.md:1-7` (N0, `repoctl`), `:15-25` (`just install`, `python-repo init`), `:39-50` (what N0 owns, `_generated/`), `:52-57` (`workspace_member`), `:59-76` (maintaining "this meta-repository", `just validate`, N0 → N1 → N2) all die. The surviving content is: prerequisites, one bootstrap command, and the project's own commands. |
| `AGENTS.md` | REWRITE | It is the maintainer contract for a two-tree meta-repository; its organizing premise is gone. | `AGENTS.md:5-27` (what this repository is), `:29-42` ("Two contracts, do not confuse them"), `:44-57` (sources-of-truth table, 7 of 10 rows point at `template/**` or Copier), `:59-101` (change protocol items 1, 2, 5, 6, 7), `:103-131` (validation requirements) all die. Surviving: the completion-reporting contract (`:133-144`), the agent-skills pointers (`:146-163`), and the vendored-docs table (`:165-183`). Pack-owned Surface; the Terminal Project projection of it must not mention bootstrap. |
| `DESIGN_GUARDRAILS.md` | REWRITE | The design-to-guardrail mapping is the pack's most reusable document, but 5 of its 12 rows enforce the dying model. | Rows that die: `:12` (`repoctl/` owns plans, declarations, lifecycle decisions), `:14` (`_generated/` indexes), `:16` (recursive self-generation, N0 → N1 → N2), `:17` (shape fixtures through the repository CLI), `:19` (docs guard registry entries), `:20` (`test_expected_files_are_preserved` + `just validate`). Rows that survive: `:10` ownership zones (renamed to Pack-owned/User-owned Surface), `:11` dependency direction, `:13` proof system, `:15` quality checks, `:18` mutation catalog. Row `:9` (start without product semantics) survives with N0 vocabulary removed. |
| `VALIDATION.md` | REWRITE | Concern survives (a dated record of the last executed validation); every current sentence documents the two-tree loop. | `VALIDATION.md:14-23`, `:27-49`, `:55-85`, `:87-101` all describe generation, generated gates, the recursive walk, and the seven-minute budget. Nothing in the body is reusable text. |
| `skills-lock.json` | KEEP | A lockfile for externally sourced agent skills. Independent of Copier, `template/`, and recursion. | Open question whether it is Pack-owned Surface (projected into every Terminal Project, so agents get the same skills) or maintainer-only User-owned Surface. It is currently root-only; `template/` does not ship it. |
| `epics/SPEC-0001.md` | DELETE | The frozen specification of the recursive proof-carrying repository: nineteen recursive steps, N0/N1/N2/N3, plans, declarations, lifecycle, capability registration, index compilation. | `epics/SPEC-0001.md:5-9` names the recursive steps (§18.5) as the acceptance surface; `:35-37` states "The repository MUST start as an N0 capable of generating its own N1, N2, N3". This is the source document of everything the target removes. |
| `epics/epic-1.yaml` … `epic-5.yaml` | DELETE | Compiled epic manifests for delivering SPEC-0001. `epic-5.yaml:18-31` certifies "a generated repository generates its own successors across five application shapes" and explicitly non-goals "changing any planner, apply, lifecycle, or index-compilation behavior". | The `epics/` **directory** and its `.gitignore:16-18` rule for `epics/*.manifest.json` are KEEP (User-owned Surface): the epic workflow is orthogonal to the pack model. |
| `build/frobenius_cache` | DELETE | Untracked, empty stray directory. Not in `git ls-files`, not in `.gitignore`. | Pure noise; it is not a build output of this repository. |
| `.vscode/settings.json` | KEEP | Editor-only artifact hiding. Contains no template, Copier, or recursion reference. | User-owned Surface. `search.exclude` of `skills-lock.json` stays valid. |
| `.gitignore` (adjacent, not listed in scope) | REWRITE | `.gitignore:8-10` ignores `uv.lock` because "the generator root is intentionally lock-file-free (stdlib-only, no runtime deps)". The Root Pack has a lockfile. | Also `dist/` and `*.egg-info/` (`:12-13`) currently exist for the generator wheel. |

## Sub-file breakdown

### `instantiate.py` (335 lines)

| Lines | Symbol | Verdict | Detail |
|---|---|---|---|
| 1-8 | module docstring | DELETE | Names "the repository template through Copier" and the two entry points. |
| 23-25 | `from copier import run_copy`, `CopierError`, `DirtyLocalWarning`, `plumbum.local` | DELETE | The only Copier and plumbum imports in the whole root scope. |
| 27 | `PACKAGE_PATTERN` | MOVE-TO-BOOTSTRAP | Duplicates the `package` validator in `copier.yml:36-39`. One copy survives as the identity-field validator. |
| 28 | `DISTRIBUTION_NAME` | DELETE | Only used by `packaged_template_version()`. |
| 29 | `TEMPLATE_SOURCE` | DELETE | Hard-codes the git URL as the durable Copier `_src_path` for downstream updates. In the target, Pack Update is performed by the externally installed Root Pack, not by an answers file recorded in the project. |
| 30-53 | `GIT_CONTEXT_LOCK`, `LOCAL_GIT_ENVIRONMENT`, `is_local_git_environment` | MOVE-TO-BOOTSTRAP | Genuinely reusable: stops the bootstrap's git commands binding to the caller's repository. Duplicated in `scripts/release.py:12-34`. |
| 56-58 | `derive_package_name` | MOVE-TO-BOOTSTRAP | Mirrors the `package` default in `copier.yml:35`. |
| 61-66 | `packaged_template_version` | DELETE | Returns `f"v{distribution_version(...)}"`. This is the **root project version as the wheel fallback for Copier's `_commit`** coupling called out in `AGENTS.md:79-81`. Pure provenance machinery. |
| 69-88 | `environment_without_local_git_context`, `without_local_git_context` | REWRITE→MOVE-TO-BOOTSTRAP | The `os.environ` scrubber survives. The `plumbum` half (`:82-85`) exists only because Copier drives git through plumbum, and dies with it. |
| 91-125 | `generate` | DELETE | The heart of the two-tree model: `source = Path(__file__).resolve().parent` (`:93`) asserts the installed package directory *is* the Copier template root; `run_copy(..., vcs_ref="HEAD", defaults=True, quiet=True, skip_tasks=True)` (`:104-117`); `_packaged_template_version` / `_packaged_template_source` (`:110-111`); the `DirtyLocalWarning` suppression (`:99-103`) that exists only for editable installs rendering the live worktree. The non-empty-output guard (`:94-95`) survives into Bootstrap. |
| 128-155 | `GIT_COMMIT_MESSAGE`, `run_command`, `initialize_git_repository`, `bootstrap_repository` | MOVE-TO-BOOTSTRAP | Reusable as-is. `bootstrap_repository` shells `just bootstrap` in the new project — the Terminal Project's own recipe. |
| 158-195 | `create_initial_commit`, `prepare_repository` | MOVE-TO-BOOTSTRAP | Reusable as-is, including the fallback identity for hosts without `user.email` (`:168-174`). |
| 198-211 | `github_create_command` | MOVE-TO-BOOTSTRAP | Reusable as-is. `AGENTS.md:24-25` requires tests to PATH-stub `gh`. |
| 214-227 | `print_next_steps`, `run_init` | DELETE | Only reachable from the legacy positional form; `print_next_steps` also prints a stale `just bootstrap` hint that the CLI path already performed. |
| 230-238 | `main` (legacy positional) | DELETE | Exists purely so the pack's tests and `scripts/validate_pack.py:220-226` can generate locally with no git and no network (`AGENTS.md:22-25`). With `validate_pack.py` gone, so is its only reason to exist. |
| 241-328 | `cli` | MOVE-TO-BOOTSTRAP | The whole `python-repo init <name> [directory] [--package] [--public] [--no-github] [--no-git]` contract is the One-shot Bootstrap CLI. `:295` `generate(...)` is the only line to replace: Copier rendering becomes Terminal Projection (copy the Root Pack tree, drop the bootstrap capability, substitute identity fields). |
| 331-334 | dual dispatch on `sys.argv[1] == "init"` | DELETE | Exists only to keep both entry points alive from one file. |

### `copier.yml` (58 lines)

| Lines | Key | Verdict |
|---|---|---|
| 1 | `_min_copier_version: "9.17.0"` | DELETE — one of the multi-location Copier pins tracked by `tests/test_pin_coherence.py` (`AGENTS.md:71-79`). |
| 2 | `_subdirectory: template` | DELETE — the literal declaration of the parallel tree. |
| 3 | `_migrations: []` | DELETE — versioned Copier update steps; superseded by Pack Update replacing whole Pack-owned Surface files. |
| 4-5 | `_envops.undefined: StrictUndefined` | DELETE — Jinja policy. |
| 6-22 | `_exclude` | DELETE as config, but **load-bearing**: it is the single source of truth for artifact patterns and is parsed at runtime by `scripts/validate_pack.py:40-55`. A Terminal Project needs the same pattern list, but it belongs in `.gitignore` plus the projection filter, not in a Copier key. |
| 24-30 | `project_name` + validator | SURVIVES as a project-identity field. |
| 32-39 | `package` + default + validator | SURVIVES as a project-identity field. Duplicated in `instantiate.py:27,56-58`. |
| 41-48 | `agents_contract` (`full`/`hooks-first`/`none`) | DELETE — a rendering variant. Terminal Projection keeps every non-identity surface byte-identical, so a three-way conditional `AGENTS.md` cannot exist. |
| 50-57 | `workspace_member` | DELETE — the largest variant switch in the pack (it omits `.python-version`, `prek.toml`, `pyproject` tables, and justfile steps). Same reason. This is a real feature loss to decide on deliberately. |

### `pyproject.toml` (root, 208 lines)

| Lines | Section | Verdict |
|---|---|---|
| 1-5 | header comment | DELETE — "Packaging metadata for the *generator only*… ships instantiate.py, copier.yml, and template/… The root still has no virtualenv or lock file". |
| 6-8 | `[build-system]` hatchling | REWRITE — the generated repositories use `uv_build` (`CHANGELOG.md:103`); the Root Pack should use the same backend it projects. |
| 10-13 | `[project]` name/version/description | REWRITE — "Generator CLI for the Python design-guardrails repository template". Note `version = "0.3.0"` is the wheel fallback for Copier `_commit` (`instantiate.py:61-66`, `AGENTS.md:79-81`); that coupling dies. |
| 15 | `dependencies = ["copier==9.17.0"]` | DELETE — the sole runtime dependency, and one of the coherent multi-location pins. |
| 17-18 | `[project.scripts] python-repo = "instantiate:cli"` | MOVE-TO-BOOTSTRAP — the console script is the Bootstrap entry point and must be removed by Terminal Projection. |
| 20-21 | `[tool.hatch.build.targets.wheel] include` | DELETE. |
| 23-28 | `force-include "template" = "template"` | DELETE — the most explicit two-tree packaging coupling. Its comment states the template must sit next to `instantiate.py` in site-packages so `Path(__file__).parent` stays the Copier template root. |
| 30-31 | `[tool.hatch.build.targets.sdist] include` | DELETE. |
| 33-36 | `[tool.pytest.ini_options] markers` | DELETE — the `repository_gate` marker exists to schedule tests that "generate repositories and run heavyweight certification gates". |
| 38-40 | Ruff header comment | REWRITE — "Keep the pack and the repositories it generates on one Ruff policy" becomes trivially true when there is one tree. |
| 41-53 | `[tool.ruff] line-length`, `src`, `force-exclude` | REWRITE — `src` (`:43-52`) lists `template/repoctl`, `template/src`, `template/tests`, `template/verification`, `template/scripts`; all five entries die and collapse to the root's own roots. |
| 55-145 | `[tool.ruff.lint] select` | **KEEP** — the curated 90-line rule selection is the single most reusable artifact in the root scope. Verbatim into the Root Pack. Pack-owned Surface. |
| 147-162 | `per-file-ignores` | REWRITE — `:150-155` (root tests, `instantiate.py`, `scripts/*`, `release.py`, `validate_pack.py`) mostly dies with its files; `:156-162` (`template/tests/**`, `template/verification/**`, `template/scripts/**`, `template/scripts/quality_gate.py.jinja`) merges with the downstream copy. The `.py.jinja` path at `:162` is a direct two-tree artifact. |
| 164-195 | `flake8-type-checking`, `isort`, `mccabe`, `flake8-tidy-imports`, `format` | KEEP — except `known-first-party` (`:174-181`), which lists `instantiate`, `repoctl`, `scripts`, `tests`, `verification`: `instantiate` and `repoctl` both die. |
| 197-208 | `[tool.basedpyright]` | REWRITE — the entire rationale ("`template/` is an uninstantiated scaffold… holds Jinja expressions… type-checking it in place is meaningless… its correctness is proven by generating a real project") evaporates. `exclude = [..., "template"]` (`:205`) and `extraPaths = ["scripts", "template"]` (`:208`) die. **Consequence: today the root type-checks almost nothing. In the target the Root Pack must run the full downstream BasedPyright policy on itself.** |

### `justfile` (root, 64 lines)

| Lines | Recipe / variable | Verdict |
|---|---|---|
| 1-6 | shell settings, `PYTHONPYCACHEPREFIX` | KEEP — though the `.venv/pycache` target presumes a `.venv` the root does not have; it will once the Root Pack is a real project. |
| 8 | `ruff := 'uv run --no-project --python 3.14 --with "ruff>=0.15.21" ruff'` | REWRITE — `--no-project` and the ephemeral `--with` provisioning exist only because the root is venv-less. The Root Pack runs `uv run ruff` from its own locked environment. |
| 9 | `ruff_sources := "instantiate.py scripts tests template"` | DELETE — names both trees explicitly. |
| 10 | `root_pytest := ... --with copier==9.17.0 --with "icontract>=2.7.3" pytest` | REWRITE — the `copier` pin dies; the `icontract` floor exists for the domain-owned repository path classifier (`AGENTS.md:126-128`) and moves to a normal dev dependency. |
| 11 | `recursive_acceptance := "tests/recursive/test_recursive_generation.py::test_recursive_walk_executes_the_specification_through_repoctl"` | DELETE — the single most explicit recursion coupling in the root. |
| 12 | `repository_gate_marker` | DELETE. |
| 14-15 | `default` | KEEP. |
| 17-24 | `check` | KEEP as a concern, REWRITE as text — the fix/format/check-stability sequence survives; the comment "Running from the pack root keeps its cache out of template/, whose filesystem must remain artifact-free" (`:18-19`) dies. **Note: the root `check` runs Ruff only.** The Terminal Project's `check` is a full gate (`CHANGELOG.md:85-92`). The target has one `check`, the downstream one. |
| 26-32 | `test` | REWRITE — three phases exist only to schedule the recursive walk against the `repository_gate` matrix. Collapses to one `pytest`. |
| 34-38 | `test-fast` | REWRITE — its selected node IDs (`test_expected_files_are_preserved`, `test_no_unrendered_jinja_survives`, `test_fast_recipe_renders_default_template_and_runs_policy_checks`) are all rendering tests and die; `test_pin_coherence`, `test_hook_policy`, `test_root_ruff_policy` survive in reduced form. |
| 40-43 | `validate` | DELETE — `uv run … python scripts/validate_pack.py`. The whole "generate into a temp dir and run the generated gate" loop is gone. Its replacement is: the Root Pack's own `just check`, plus a Bootstrap acceptance test that projects once. |
| 45-48 | `release` | KEEP — Pack-owned Surface. |
| 50-54 | `install` (`uv tool install --force --editable .`) | MOVE-TO-BOOTSTRAP — "editable: template edits and `git pull` take effect without reinstalling" is a two-tree convenience, but installing the Root Pack externally is exactly how Pack Update is performed (per CONTEXT). The recipe survives in the Root Pack and is removed by Terminal Projection. |
| 56-64 | `hooks` | KEEP — Pack-owned Surface; idempotent prek install with the `>=0.4.9` floor (a tracked multi-location pin). |

### `scripts/validate_pack.py` (525 lines)

| Lines | Unit | Verdict |
|---|---|---|
| 1-20 | docstring (the 10-step loop) | REWRITE — steps 1, 2, 3, and 10 die; steps 4-9 survive. |
| 32-37 | `REPO_ROOT`, `TEMPLATE_ROOT`, `COPIER_CONFIG`, `PROJECT_NAME`, `PACKAGE_NAME`, `DOCTOR_BUDGET_SECONDS` | REWRITE — `TEMPLATE_ROOT` and `COPIER_CONFIG` die; the throwaway project identity moves into the Bootstrap acceptance test; `DOCTOR_BUDGET_SECONDS = 5.0` survives. |
| 40-55 | `artifact_exclusion_patterns` | DELETE — parses `_exclude` out of `copier.yml` by hand-scanning YAML lines. |
| 58-65 | `find_forbidden_artifacts` | DELETE — enforces that `template/` holds no runtime caches. With one tree, `.gitignore` plus the projection filter own this. |
| 68-87 | `find_unrendered_jinja` | DELETE — the entire "no `.jinja` suffix and no `{{`/`{%`/`{#` survives" contract. Nothing analogous exists when nothing is rendered. |
| 90-105 | `seed_repair_probes` | REWRITE — the *idea* (plant deterministic drift, prove `just check` repairs it) survives as a normal Root Pack test. Its probe target is `src/<pkg>/_generated/active_capabilities.py` (`:92`) and it raises "repair probe could not find the generated N0 index declaration" (`:103`) — both die with generated capability indexes. Pick a surviving file. |
| 108-113 | `fail` | KEEP — the "what broke / how to fix" reporting convention. |
| 116-161 | `run_step`, `run_captured_step` | KEEP — including the `VIRTUAL_ENV`/`UV_PROJECT_ENVIRONMENT`/`PYTHONPATH` scrub (`:119-123`), which is needed whenever a test drives a second project. |
| 164-191 | `effective_git_path`, `worktree_hook_errors` | KEEP — prek shim sharing across linked worktrees is a genuine Terminal Project guardrail with no template dependency. |
| 198-207 | template cleanliness step | DELETE. |
| 209-215 | toolchain preflight (`git`, `just`, `uv`) | MOVE-TO-BOOTSTRAP — the same preconditions the Bootstrap capability needs. |
| 217-237 | temp-dir instantiate via the legacy positional CLI | MOVE-TO-BOOTSTRAP — becomes "project once into a temp dir" acceptance for the Bootstrap capability. `:220-226` is the only caller of `instantiate.py`'s legacy form. |
| 239-248 | unrendered-Jinja step | DELETE. |
| 250-283 | git init, seed probes, `just bootstrap`, verify repairs | MOVE-TO-BOOTSTRAP (the git-init and bootstrap half) + REWRITE (the repair probe as a root test). |
| 285-312 | missing-hook repair probe | KEEP as a Root Pack test — deletes both prek shims and proves `just check` restores them. No template dependency. |
| 314-336 | commit the baseline through the installed hooks | MOVE-TO-BOOTSTRAP. |
| 338-374 | tracked un-imported syntax probe | KEEP as a Root Pack test — proves the gate parses every tracked `*.py`. |
| 376-433 | doctor green + dirty probes with a PATH-stubbed `gh` | KEEP as a Root Pack test — the `gh` stub pattern (`:378-384`) is the same technique `AGENTS.md:24-25` mandates. |
| 435-515 | linked-worktree shim creation and execution | KEEP as a Root Pack test. |
| 517-520 | success banner | REWRITE. |

## Hard-coded two-tree couplings (checklist)

1. `copier.yml:2` — `_subdirectory: template`.
2. `copier.yml:6-22` — `_exclude` as the artifact-pattern source of truth, re-parsed at `scripts/validate_pack.py:40-55`.
3. `pyproject.toml:20-21` — wheel ships `instantiate.py` + `copier.yml`.
4. `pyproject.toml:27-28` — `force-include "template" = "template"`, bypassing ignore rules so dotfiles and Jinja-named directories ship verbatim.
5. `pyproject.toml:30-31` — sdist ships `template`.
6. `pyproject.toml:15` — `copier==9.17.0` as the root's sole runtime dependency.
7. `pyproject.toml:43-52` — Ruff `src` enumerates five `template/*` roots.
8. `pyproject.toml:156-162` — per-file-ignores for `template/**`, including a `.py.jinja` path.
9. `pyproject.toml:205,208` — BasedPyright excludes `template` from analysis but keeps it on the import path.
10. `instantiate.py:93` — `source = Path(__file__).resolve().parent` makes the installed package directory the Copier template root.
11. `instantiate.py:104-117` — `run_copy(..., vcs_ref="HEAD", skip_tasks=True)`.
12. `instantiate.py:61-66,110-111` — wheel version → `v{version}` → the `_commit` provenance fallback; `TEMPLATE_SOURCE` (`:29`) → the durable `_src_path`.
13. `justfile:9` — `ruff_sources` includes `template`.
14. `justfile:10` — root pytest provisions `copier==9.17.0`.
15. `justfile:11` — hard-coded recursive-walk node ID naming `repoctl`.
16. `justfile:42-43` — `just validate` = generate into a temp dir and run the generated gate.
17. `justfile:52-54` — `install` relies on editable installs so template edits take effect without reinstalling.
18. `scripts/reminder_comment_hook.py:15` — `sys.path.insert(0, REPO_ROOT / "template")`.
19. `prek.toml:21-23` — the pre-push hook advertises the N0 → N1 → N2 walk and its seven-minute budget.
20. `.github/workflows/quality.yml:27-32` — full history and tags for Copier update-roundtrip tests.
21. `.gitignore:8-10` — `uv.lock` ignored because the generator root is deliberately lock-file-free.
22. `AGENTS.md:106-131` — `just validate` as the sole completion criterion for any `template/` or `instantiate.py` change.

## Vocabulary to retire

| Term in root scope | Where (examples) | Replacement |
|---|---|---|
| meta-repository | `AGENTS.md:6,8`; `README.md:61` | Root Pack |
| the pack / template pack | `AGENTS.md:3,44`; `scripts/validate_pack.py:2`; `prek.toml:9,18,22` | Root Pack |
| template tree / `template/` / the template | throughout | (no replacement — one source tree) |
| template release / template tag | `CHANGELOG.md:1,3`; `scripts/release.py:79,82`; `justfile:45` | Pack release |
| generated repository / generated repositories | `AGENTS.md:9,26,34,110`; `README.md:27`; `DESIGN_GUARDRAILS.md:14` | Terminal Project |
| downstream (as a noun/qualifier) | `AGENTS.md:38,51-53,141`; `justfile:36`; `prek.toml` | Terminal Project |
| generate / generation / generator / instantiate / instantiation | `AGENTS.md:12,64`; `pyproject.toml:1,13,197`; `README.md:1` | Terminal Projection (the operation) / One-shot Bootstrap (the capability) |
| N0 | `README.md:2,39,41,73`; `AGENTS.md:120`; `DESIGN_GUARDRAILS.md:4,14`; `validate_pack.py:103` | Terminal Project |
| N0 → N1 → N2 / recursive / recursive self-generation / recursive walk | `AGENTS.md:120`; `justfile:11,26`; `prek.toml:21`; `DESIGN_GUARDRAILS.md:16`; `epics/SPEC-0001.md` | (no replacement — One-shot Bootstrap does not recurse) |
| repoctl | `README.md:5,31,36,43`; `DESIGN_GUARDRAILS.md:9,12`; `pyproject.toml:47,177`; `justfile:11` | (no replacement — removed) |
| plans / declarations / lifecycle decisions | `DESIGN_GUARDRAILS.md:12`; `epics/epic-5.yaml:30` | (no replacement — a Product Capability's owned code is its source of truth) |
| generated indexes / `_generated/` / capability index | `README.md:46`; `DESIGN_GUARDRAILS.md:14`; `validate_pack.py:92,103` | (no replacement — removed) |
| registry / registry entries / registered capability | `DESIGN_GUARDRAILS.md:19` | Product Capability |
| child repository / nested repository / successor | `epics/epic-5.yaml:19` | Product Capability |
| Copier / Jinja / `vcs_ref` / `_commit` / `.jinja` | `AGENTS.md`, `copier.yml`, `instantiate.py`, `CHANGELOG.md:8-10` | (no replacement) |
| scaffold / `just scaffold-update` / scaffold migration | `pyproject.toml:200,206`; `CHANGELOG.md:18,111` | Pack-owned Surface / Pack Update |
| ownership zones | `DESIGN_GUARDRAILS.md:10,14` | Pack-owned Surface / User-owned Surface |
| throwaway repository | `AGENTS.md:62,98`; `validate_pack.py:8,229` | (no replacement) |
| self-generation / self-replication | `DESIGN_GUARDRAILS.md:16` | One-shot Bootstrap |

## Guardrails that are root-only today and must become normal Terminal Project guardrails

1. **Ruff policy ownership.** `pyproject.toml:41-195` is the *only* copy of the curated lint policy that also covers the root's own Python. In the target it is one ordinary `[tool.ruff]` block in the Root Pack, projected byte-identically into Terminal Projects.
2. **Type checking.** `pyproject.toml:204-208` is a four-key stub that excludes the only large tree. The root has never been type-checked under the downstream BasedPyright `recommended` + `failOnWarnings` policy (`CHANGELOG.md:41-45`). Making the Root Pack self-hosting means `instantiate.py`'s successor, `scripts/`, and `tests/` must pass it.
3. **Coverage, architecture guard, ownership guard, docs guard, proof guard, Import Linter, CrossHair.** All exist only under `template/scripts/` and only run in a generated repository. All become root guardrails. The Bootstrap capability's code must itself satisfy them — including the architecture guard's ownership zones and the proof system, which is a non-trivial demand on a subprocess-heavy CLI.
4. **`just check` as a mechanical gate.** The hardened downstream `check` (prek shim verification and repair, tracked-Python syntax compile — `CHANGELOG.md:85-88`) has no root counterpart; the root `check` (`justfile:17-24`) is Ruff only.
5. **`just doctor`.** Root-absent; downstream-only (`CHANGELOG.md:89-92`, probed at `validate_pack.py:376-433`). Becomes a normal root recipe.
6. **Release discipline.** `scripts/release.py` (changelog entry + clean tree + unique tag) is root-only and has no downstream counterpart. It becomes a Pack-owned Surface guardrail — and the question of whether a Terminal Project inherits it is open.
7. **ARCH031 edit-time enforcement.** `scripts/reminder_comment_hook.py` applies the downstream rule to root files by reaching into `template/`. In the Root Pack it is simply the project's own hook over its own rule module.
8. **Pin coherence.** `AGENTS.md:71-79` describes `tests/test_pin_coherence.py` scanning the tracked tree for duplicated pins. Most of the pins it guards (Copier, the template tag) disappear; uv, the prek floor, and the session-profiler commit remain, and the test must survive in reduced form. (`tests/` is another agent's scope; flagged here because the root justfile and `prek.toml` are its subjects.)

## Open questions / uncertainties

1. **`workspace_member` and `agents_contract` are real feature losses.** `copier.yml:41-57` supports three agent-contract variants and a uv-workspace-member mode that omits `.python-version`, `prek.toml`, several `pyproject` tables, and justfile steps. CONTEXT.md states Terminal Projection substitutes "only a closed set of project-identity fields" and keeps every other surface identical. Either these variants are dropped, or "project-identity fields" is broader than it reads. This needs an explicit decision.
2. **Is the Root Pack's own `pyproject.toml` a Pack-owned Surface file?** It contains both project identity (name, version, description) and pack policy (Ruff, BasedPyright). It cannot be replaced wholesale by a Pack Update without clobbering identity, so it is the clearest case of a file that is neither purely Pack-owned nor purely User-owned.
3. **What replaces `_commit` provenance?** Today a generated repository records which template commit produced it (`instantiate.py:110-111`), which is how a Copier update knows what to diff. If Pack Update replaces whole Pack-owned Surface files from the externally installed Root Pack, the version of the installed pack may be sufficient — but nothing currently records, in the Terminal Project, which pack version last touched it. Undecided.
4. **Does `skills-lock.json` project downstream?** It is root-only today and `template/` ships no equivalent. Both answers are defensible.
5. **Does the Root Pack keep a `python-repo` console script name?** `pyproject.toml:18` and the CLI contract in `instantiate.py:241-284` are documented in `README.md:15-25` and `AGENTS.md:16-25`. The name is fine; whether the verb stays `init` or becomes something like `project` is a naming decision that CONTEXT.md does not settle.
6. **Where does Pack Update live?** CONTEXT.md says the externally installed Root Pack performs it. That implies a second subcommand alongside `init` in the same Bootstrap capability — but Pack Update operates on an *existing* Terminal Project, whereas `init` creates one. Whether both are removed by Terminal Projection is not stated; logically yes (the Terminal Project must not be able to update itself), but this should be confirmed.
7. **`epics/` retention.** The five epic manifests and SPEC-0001 are the historical record of building the model being removed. Deleting them loses provenance; keeping them leaves the retired vocabulary in the tree, where `DESIGN_GUARDRAILS.md:19` says a guard rejects retired vocabulary across root Markdown. They likely need archiving outside the tracked tree or an explicit guard exemption.
8. **Seven-minute budget.** `prek.toml:22` and `AGENTS.md:120-123` set the pre-push budget around the recursive walk, which `VALIDATION.md:99-101` calls "an irreducible roughly three-minute floor". Removing the walk should free most of that; the new budget is unmeasured.
