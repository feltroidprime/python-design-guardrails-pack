# Template changelog

Template releases use PEP 440 git tags in the form `vX.Y.Z`. Every release
must have a matching `## [vX.Y.Z]` entry here before `just release vX.Y.Z`
will create the tag. Entries describe changes that generated repositories can
adopt, including accepted or rejected optimization-loop experiments.

Generation from a release must pin that tag with Copier's `vcs_ref`. Generation
from a local working tree intentionally records a `git describe` development
identity, including the dirty marker when the experiment has uncommitted changes.

## [Unreleased]

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
