# Changelog

This file records the changes of this repository, newest first. It uses PEP 440
release tags in the form `vX.Y.Z`, and every release needs a matching
`## [vX.Y.Z]` heading here before `just release vX.Y.Z` creates the tag.

An entry describes a change that a project born from this pack can adopt. A
project inherits the pack version it was born from, and `pack/manifest.json`
records the pack version that its last update carried.

## [Unreleased]

### One tree, one contract

- Collapse the two parallel trees into one Root Pack. The pack is now a real
  installable Python 3.14 project, so every tool checks the shipped files in
  place and a defect is fixed exactly once. The parallel product tree, its 157
  rendered files, the rendering engine and its answers file are all deleted.
- Replace the control plane inside every project with one command capability
  that only the pack carries. A project it starts cannot start another one.
  Plans, applied plans, declarations, lifecycle records and derived indexes are
  deleted with it.
- Start a project with `pyrepo bootstrap init NAME [DIRECTORY]` from an
  installed console script. It refuses a bad name before it writes anything,
  builds the whole tree in a temporary directory, checks it, and moves it into
  place as one operation. It reaches no network unless `--github` is given.
- Add `pyrepo bootstrap update DIRECTORY`. It replaces whole pack-owned files,
  writes no user-owned file, refuses on local drift, and restores every path if
  it fails. So current tool policy reaches a project that already exists.
- Replace the four ownership classes and their roughly forty roots with two
  surfaces and one predicate, recorded in ADR-0008. Three hand-written
  validators are deleted.
- Move every tool policy under `pack/configs/`, which is a stable path ABI. The
  root `justfile`, `pyrightconfig.json`, `.python-version` and quality workflow
  are now thin entry points that an update reports and never writes.
- Replace the hand-written gate runner with twelve `prek` hooks. `just check`
  and CI both run `prek run --all-files -c pack/configs/prek.toml`, and the gate
  is identical in the pack and in every project.
- Derive the command line from composition. `_foundation/router.py` reads the
  `CAPABILITIES` tuple of the user-owned composition root and builds every
  group, option, envelope and exit code from stdlib-typed signatures. The
  command catalog and its registration rules are deleted.
- Add a Product Capability as one directory plus one import line. Six
  `import-linter` contracts carry the four layout rules that hand-written code
  carried before.
- Delete every coverage assertion. `DESIGN_GUARDRAILS.md` states the rationale,
  and the acceptance suite proves that no coverage flag, plugin or table
  returns.
- Replace Ruff's deleted upkeep-comment rule with Ruff's own `TD` and `FIX`
  families, and delete its edit-time hook.
- Add `pack/manifest.json` and a `manifest` hook, so a stale record of the
  pack-owned bytes fails at commit time rather than at update time.
- Add the acceptance suite: 53 assertions in six groups, marked `acceptance`,
  each run from an installed console script.
- Rewrite every document against the vocabulary of `CONTEXT.md`, restore
  ADR-0002 and ADR-0004 as superseded records, and add ADR-0008.
- Close the type and architecture backlog that the collapse exposed in nine
  pack test modules, which the deleted root never analysed. The gate is green
  on all twelve hooks, in the pack and in a project it starts. No ceiling was
  raised, no rule removed and no finding suppressed.
- Provision `just 1.57.0` in the pack-owned CI action, through `uv` and its
  `rust-just` distribution. The `tests` hook runs `just` against a fixture tree,
  and a Linux runner carries no such command, so both CI jobs were red. A pack
  update carries the fix to a project that already exists.
- Give a new project a quality workflow that holds the `quality` job only. The
  projection now overlays `.github/workflows/quality.yml` with one of the
  starting files, so the job for the acceptance suite stays in the pack with
  the suite it runs. In a project that job collected no
  test in a project, pytest answered exit code 5, and every new project was red
  on its first push. Assertion `REM-7` reads the projected workflow and fails
  on any job that runs a marker the deletion empties. The `just` pin now has
  one required location rather than two, because the second sits in the job
  that a project no longer carries.
- Narrow the `manifest` hook to the pack-owned bytes it is named for. The
  `shims` list of `pack/manifest.json` records what the pack shipped, and a
  shim is user-owned: a project starts with an overlaid workflow, and a
  justfile invites its owner to add recipes. The hook no longer reads either as
  drift. A Pack Update still reports a customised shim and still never writes
  one.

The unreleased entries that this section replaces described the tree that the
refactor deleted. The released versions below are unchanged history.

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
