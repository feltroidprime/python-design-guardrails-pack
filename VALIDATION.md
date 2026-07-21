# Validation record — 2026-07-20

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just
1.56.0, Bun 1.3.9, Git 2.55.0, Copier 9.17.0, pytest 9.1.1, and
pytest-xdist 3.8.0. Copier emitted 26 expected `DirtyLocalWarning` instances
because the canonical template changes were intentionally uncommitted.

## Change validated

Four changes against the same root design concern — invariants entrusted to
human memory instead of being enforced by construction:

1. The Copier update round-trip test now **derives** its planted candidate tag
   from the clone's real release tags (highest `vX.Y.Z` plus a patch bump)
   instead of a hardcoded `CURRENT_RELEASE_CANDIDATE` constant that had to be
   bumped manually after every release. The reminder comment and the matching
   maintenance rule in `AGENTS.md` were deleted because the invariant is now
   true by construction.
2. The generated architecture guard gained **ARCH031**: comments that schedule
   manual upkeep ("bump this after each release", "keep in sync with",
   "remember to", "must be updated") fail the gate. The check inspects comment
   tokens only — string literals and docstrings are exempt — matches a closed
   phrase set recorded in ADR-0005, and accepts `ARCH-EXCEPTION: ADR-XXXX`
   like the other review-harvest codes.
3. `tests/test_pin_coherence.py` mechanizes the "keep version pins coherent"
   rule: it discovers every multi-location pin (Copier, uv, prek floor, grimp,
   pytest-xdist, the session-profiler commit, the single-source LikeC4 CLI
   version) by scanning the tracked tree and fails when any copy disagrees.
   `AGENTS.md` rule 4 shrank from an enumerated location list to a pointer at
   the test plus the two release-time judgment calls.
4. A project Claude Code `PostToolUse` hook (`.claude/settings.json` →
   `python3 -B scripts/reminder_comment_hook.py`) rejects reminder comments in
   the pack's own Python files at edit time, reusing the template's ARCH031
   patterns as the single source. Proven end-to-end: a probe file containing
   "bump this after each release" was blocked with the corrective message.
   The first hook run without `-B` wrote `template/scripts/__pycache__/` and
   the template-cleanliness tests failed the next validation exactly as
   designed; `-B` fixed it and the artifacts were removed.

## Commands and actual results

### Canonical pack validation — default configuration

```bash
just validate
```

Final result: passed (re-run after each wave; final run with all four changes).

- Pack tests: 273 passed with 26 expected warnings in ~64s.
- Template cleanliness and complete Jinja rendering: passed.
- Generated bootstrap installed both prek hooks and passed the complete
  generated gate, including the architecture guard with ARCH031 active over
  the generated `src/`, `tests/`, and `scripts/` trees.
- Generated tests: 145 passed, 7 skipped, 3 session tests deselected; branch
  coverage 93.44%.
- The missing-hook repair, tracked syntax rejection, doctor clean/dirty,
  linked-worktree pre-commit, linked-worktree full pre-push, and cleanup probes
  passed.
- Previous-release and generated-recipe Copier update acceptance with the
  derived candidate tag: 2 passed in 31.23s.

### Canonical pack validation — LikeC4 configuration

```bash
just validate likec4
```

Final result: passed. The opt-in configuration's extra files (including
`scripts/sync_architecture_diagrams.py`) pass the guard with ARCH031 active,
and the `diagram regeneration`, `diagram sync`, and `diagram views` checks all
ran, the latter via `bunx likec4` (step banners confirmed in the run output).

An intermediate run failed honestly: the first ARCH031 implementation used
implicit string concatenation in a multi-line regex, which the generated
BasedPyright gate rejects (`reportImplicitStringConcatenation`). The pattern
was rebuilt from named parts and both validations re-run to completion.

## Tests added or updated

- `tests/test_update_roundtrip.py`: `candidate_release_tag()` computes the
  planted tag from `git tag --list 'v*'`; the constant it replaces is gone.
- `tests/test_review_discipline.py`: violating, clean (descriptive comments and
  pattern words inside string literals), and ADR-marker suppression fixtures
  for ARCH031; the shared suppression test now covers ARCH026–ARCH031.
- `tests/test_instantiate.py`: the recorded generated-tree digest tracks the
  template content change.

## Remaining risks and portability notes

- ARCH031 is deliberately lexical, English-only, and comment-token-only: a
  closed phrase list bounded by ADR-0005's revisit trigger. Reworded reminders
  ("adjust the constant at release time") can evade it; prose in docstrings
  and Markdown is out of scope.
- The candidate-tag derivation assumes release tags stay `vX.Y.Z`; a
  differently shaped tag scheme would fall back to the assertion failure in
  `candidate_release_tag`, not to a silent wrong tag.
- The previously recorded LikeC4 opt-in validation results (file delta, Bun
  prerequisite scoping, ADR renumbering caveats) still hold; see the git
  history of this file for that record.
