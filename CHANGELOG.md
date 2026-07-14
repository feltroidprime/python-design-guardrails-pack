# Template changelog

Template releases use PEP 440 git tags in the form `vX.Y.Z`. Every release
must have a matching `## [vX.Y.Z]` entry here before `just release vX.Y.Z`
will create the tag. Entries describe changes that generated repositories can
adopt, including accepted or rejected optimization-loop experiments.

Generation from a release must pin that tag with Copier's `vcs_ref`. Generation
from a local working tree intentionally records a `git describe` development
identity, including the dirty marker when the experiment has uncommitted changes.

## [Unreleased]

- Document downstream Copier update checks, inline conflict resolution, and the
  generated repository's merge-conflict guard.
- Wire the template's empty migration list for future versioned update steps.

## [v0.1.0] - 2026-07-14

- Establish Copier generation as the first tagged template baseline.
