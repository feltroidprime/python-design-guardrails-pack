# Template changelog

Template releases use PEP 440 git tags in the form `vX.Y.Z`. Every release
must have a matching `## [vX.Y.Z]` entry here before `just release vX.Y.Z`
will create the tag. Entries describe changes that generated repositories can
adopt, including accepted or rejected optimization-loop experiments.

Generation from a release must pin that tag with Copier's `vcs_ref`. Generation
from a local working tree intentionally records a `git describe` development
identity, including the dirty marker when the experiment has uncommitted changes.

## [Unreleased]

- Add ARCH031 to the generated architecture guard: reminder comments that
  schedule manual upkeep ("bump this after each release", "keep in sync with",
  "remember to", "must be updated") fail the gate. The check inspects comment
  tokens only — string literals and docstrings are exempt — matches a closed
  set of phrases recorded in ADR-0005, and accepts `ARCH-EXCEPTION: ADR-XXXX`.
  Derive the value from its source of truth or enforce the invariant with a
  test instead of asking a future editor to remember.
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
