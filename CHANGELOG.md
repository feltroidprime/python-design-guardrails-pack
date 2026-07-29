# Template changelog

Template releases use PEP 440 git tags in the form `vX.Y.Z`. Every release
must have a matching `## [vX.Y.Z]` entry here before `just release vX.Y.Z`
will create the tag. Entries describe changes that generated repositories can
adopt, including accepted or rejected optimization-loop experiments.

Generation from a release must pin that tag with Copier's `vcs_ref`. Generation
from a local working tree intentionally records a `git describe` development
identity, including the dirty marker when the experiment has uncommitted changes.

## [Unreleased]

- Make the prek commit and pre-push hook policy unconditional. The `precommit`
  Copier question is removed: every standalone generated repository now ships
  `prek.toml`, the `prek` dev dependency, and the `prek install`/`prek update`
  steps in `just bootstrap`/`just update`. Workspace members still omit them,
  because the workspace root owns hooks and the lockfile. Existing repositories
  answering `precommit = false` gain the hook policy on the next
  `just scaffold-update`.
- Remove the end-to-end value benchmark harness (`benchmarks/`, its tests, and
  the `just benchmark*`/`just bench-*` recipes) from the maintainer repository.
  It never shipped to generated repositories, so downstream content is
  unaffected.
- Replace the generated repository's maximalist Ruff selection with a curated
  one: Ruff stays strict on defects, security, and modern syntax, BasedPyright
  owns type semantics, and the architecture guard owns structure. Families that
  duplicate the formatter (`Q`, `W`, general `E`) or the type checker (`ARG`,
  `SLF`, `ISC`, `ANN` beyond public return types) are dropped, and the
  taste-driven families (`FURB`, `PERF`, `ICN`, blanket `SIM`/`RET`/`TRY`/`PL`)
  are replaced by explicit high-signal rule lists. The Pylint size ceilings are
  removed in favor of `C901 = 10` plus the guard's line ceilings; `TC` is
  narrowed to `TC004`/`TC005`/`TC010` so `TYPE_CHECKING` blocks are validated
  but never forced. BasedPyright keeps `recommended` with `failOnWarnings`, but
  contract-critical diagnostics stay `warning` so editors keep a usable
  severity hierarchy while CI fails identically. Redundant settings
  (`target-version`, `fixable`/`unfixable`, `venvPath`/`venv`,
  `pythonPlatform`) are gone.
- Reorient generated repositories around a proof-carrying functional core. A
  closed `proof.toml` catalog gives every critical public behavior a normative
  property ID, exact scope, explicit assumptions, failure modes, counterexample,
  production targets, and independent executable oracles.
- Add `icontract` as the single runtime proof dependency, Hypothesis evidence
  (including a reference `RuleBasedStateMachine` for idempotent retries), and
  bounded CrossHair analysis over every pure contracted function or method.
- Add `scripts/proof_guard.py`: it rejects unclassified core behavior, orphaned
  or mismatched contracts, example-only evidence, missing falsifying canaries,
  coupled, effectful, or non-boolean oracles, constructor-only method evidence,
  same-named symbols from the wrong module, dead state-machine evidence, and
  symbolic targets outside the contract.
- Add fast/full/deep proof lanes: `just prove-one PROPERTY-ID`, `just prove`,
  `just prove-deep`, and `just proof-report`; the normal quality gate runs the
  structural proof contract and the bounded symbolic core before tests.
- Freeze the reference entity and event state, extract pure create/rename/event
  decisions, separate primitive specification predicates from implementation,
  and document the design in ADR-0006 and `docs/architecture/PROVABILITY.md`.
- Make the pack's pre-commit hook run the fast rendered-template, pin-coherence,
  and hook-policy checks. Keep the complete pack and downstream validation at
  pre-push through `just validate`.
- Add ARCH031 to the generated architecture guard: reminder comments that
  schedule manual upkeep ("bump this after each release", "keep in sync with",
  "remember to", "must be updated") fail the gate. The check inspects comment
  tokens only — string literals and docstrings are exempt — matches a closed
  set of phrases recorded in ADR-0005, and accepts `ARCH-EXCEPTION: ADR-XXXX`.
  Derive the value from its source of truth or enforce the invariant with a
  test instead of asking a future editor to remember.
- Remove the derived LikeC4 architecture model. Generated repositories no
  longer ship `docs/architecture/likec4/`, `scripts/sync_architecture_diagrams.py`,
  the gate's `diagram *` checks, `just diagrams`, the `grimp` dev dependency, or
  the CI `setup-bun` step, and **Bun is no longer a prerequisite**. Import Linter
  still enforces the layer contract.
- Renumber the shipped foundation ADRs so previous 0002-0006 become 0001-0005
  and add the proof-carrying-core decision as 0006. Repositories updating with
  `just scaffold-update` will see these renames; adjust local
  `ARCH-EXCEPTION: ADR-NNNN` markers accordingly.
- Scope the docs guard's derived-documentation exclusion to any `generated/`
  directory under `docs/`.
- Harden `just check` as a mechanical gate: before any repair or acceptance
  work it verifies the prek pre-commit and pre-push shims in Git's common hooks
  directory, repairs missing or invalid shims with `uv run prek install -f`, and
  syntax-compiles every tracked Python file, including files no test imports.
- Add a bounded `just doctor` readiness command with stable statuses for hooks,
  working-tree cleanliness, default-branch synchronization, GitHub CLI auth,
  `uv sync --check`, and Python version. Unavailable remote checks warn; local
  defects fail the verdict and return non-zero.

## [v0.2.0] - 2026-07-17

- Add a `workspace_member` Copier question (default `false`). When true, the
  generated project is a member of a uv workspace whose root owns the lockfile,
  virtualenv, dev dependency group, and shared `ruff`/`basedpyright`/`pytest`/
  `coverage` config: the generator then omits `.python-version`, the `prek.toml`
  policy, those `pyproject.toml` tables, and the `uv sync`/`uv lock`/hook-install
  steps from the justfile, so a member never creates its own environment or
  lockfile. Per-package Import Linter contracts, the `src` layout, and the
  `uv_build` build system stay. Standalone generation is byte-for-byte unchanged.
- Document consuming published monorepo member packages as uv git dependencies
  pinned to a tag via `[tool.uv.sources]` with a `packages/<name>` subdirectory.
- Add provider-neutral Claude Code and Codex session evidence through the
  opt-in, commit-pinned private `session-profiler-optimizer` module. Its Harbor 0.18.0
  converter turns immutable native snapshots into ATIF-v1.7 plus deterministic
  TSV/route/blob/manifest views with fail-closed identity and hash checks. An
  opt-in consumer E2E test samples real private logs across five size quantiles.
- Make scaffold updates executable through `just scaffold-update`. Packaged
  generation records the durable GitHub source, and the pinned Copier command
  reuses saved answers without inheriting the project's bytecode-cache path.
- Collapse downstream agent verification into one check loop: `just check`
  applies safe Ruff fixes, formats code, regenerates derived diagrams, and then
  runs the full gate. The narrower justfile removes the competing `fix`,
  `test`, and `arch` routes while pre-push and CI keep the gate strict.
- Remove the abandoned benchmark trace export and generated agent-session
  observability workflow. This deliberately removes the provider-specific
  transcript-evidence requirement from the downstream agent contract: its only
  capture and export mechanism no longer exists, so retaining the requirement
  would make the contract unactionable. A replacement workflow must define its
  own evidence boundary before adding an equivalent guardrail.
- Ship `CLAUDE.md` (`@AGENTS.md`) whenever `agents_contract != "none"`. Claude
  Code reads `CLAUDE.md` and never `AGENTS.md`, so the operating contract was
  invisible to it unless a prompt told the agent to open the file; the import
  makes the contract load in every session while `AGENTS.md` stays its single
  owner.
- Fix `agents_contract = "none"`: the documentation map is now rendered, so its
  `AGENTS.md` rows disappear with the file. The variant previously generated a
  repository that failed its own `docs guard` with two DOC001 violations.
- Document downstream Copier update checks, inline conflict resolution, and the
  generated repository's merge-conflict guard.
- Wire the template's empty migration list for future versioned update steps.

## [v0.1.0] - 2026-07-14

- Establish Copier generation as the first tagged template baseline.
