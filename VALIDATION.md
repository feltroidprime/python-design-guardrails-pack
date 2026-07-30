# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6, uv 0.12.0,
just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist 3.8.0, Ruff 0.16.0,
and prek 0.4.11.

## Change validated

Issue #62 completes the N0 documentation and pack-test migration.

- Generated and root documentation now describe a product-empty N0 baseline
  with repository control, guards, proof evidence, and generated indexes.
- The generated-file registry, workspace import contract, and executable smoke
  test describe the shipped N0 surface. The smoke test runs `repoctl status`
  and confirms an empty capability state.
- The validation harness seeds repair drift in a retained generated index,
  rather than in the removed package entry point.
- A pack test rejects retired exemplar vocabulary in root and template Markdown.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 just validate
```

The canonical command passed end to end:

- root Ruff repair/check was stable across 141 files, and the root suite passed
  **217 tests** with 14 dirty-template warnings;
- template cleanliness, fresh generation, complete Jinja rendering, generated
  bootstrap, and the downstream repair probe passed;
- the generated gate reported **0 errors, 0 warnings** from BasedPyright;
  ownership, architecture, documentation, proof-contract, symbolic-core, and
  Import Linter checks passed;
- generated tests passed **125 passed, 1 skipped, 3 deselected** with **95.65%
  coverage** (90% required);
- missing-hook repair, tracked syntax rejection, clean and dirty doctor probes,
  and linked-worktree pre-commit/pre-push probes passed.

The syntax and dirty-tree failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess and filesystem behavior can differ.
- The generated repository intentionally has no product capability. Product
  behavior remains unvalidated until a repository owner declares one.
