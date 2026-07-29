# Validation record — 2026-07-29

Validated on macOS 26.5 (Darwin 25.5.0, arm64) with Python 3.14.6, uv 0.11.32,
just 1.57.0, Copier 9.17.0, pytest 9.1.1, and pytest-xdist 3.8.0.

## Change validated

The generated repository's lint and type policy in `template/pyproject.toml.jinja`
moved from a maximalist Ruff selection to a curated one:

- families that duplicate the Ruff formatter (`Q`, `W`, general `E`) or the
  type checker (`ANN` beyond public return types, `ARG`, `SLF`, `ISC`) were
  dropped; `E4`, `E7`, `E9`, `W605`, and `ANN201`/`ANN204`/`ANN205`/`ANN206`
  remain;
- taste-driven rewrite families (`FURB`, `PERF`, `ICN`, and the blanket `SIM`,
  `RET`, `TRY`, `PL` selections) were replaced by explicit high-signal rule
  lists; `PL` is now `PLC`/`PLE`/`PLW` plus six named `PLR` rules;
- the Pylint size ceilings (`max-args`, `max-locals`, `max-returns`,
  `max-statements`, `max-public-methods`, …) were removed; `C901 = 10` and the
  architecture guard's line ceilings remain the size contract;
- `TC` was narrowed to `TC004`, `TC005`, `TC010`, so hand-written
  `TYPE_CHECKING` blocks are still validated but imports are no longer forced
  into them;
- redundant settings were dropped: `target-version` (derived from
  `requires-python`), `fixable`/`unfixable` (defaults; the quality gate owns
  the fix policy), `venvPath`/`venv`/`pythonPlatform` (BasedPyright defaults),
  and the now-dead `ignore` and per-file-ignore entries;
- BasedPyright keeps `typeCheckingMode = "recommended"` with
  `failOnWarnings = true`, but contract-critical diagnostics are `warning`
  rather than `error` so editors keep a usable severity hierarchy while CI
  fails identically; `reportUnusedImport` and
  `reportInvalidStringEscapeSequence` are disabled because Ruff owns them, and
  `reportImplicitStringConcatenation`, `reportUnusedParameter`, and
  `reportIgnoreCommentWithoutRule` are stated explicitly.

Documentation was updated in the same change: the root `README.md` design-choice
row now reads "Curated Ruff policy", `DESIGN_GUARDRAILS.md` no longer credits
Ruff design or performance rules, and the generated
`docs/architecture/README.md` fitness-function list was corrected.

Every selected rule code was checked against the pinned Ruff floor
(`ruff rule --all --output-format json`, ruff 0.15.21): all 46 individually
selected codes exist and none are preview or deprecated.

## Commands and actual results

```bash
just validate
```

Passed end to end. The generator suite, template-cleanliness and full-rendering
checks, dependency resolution, bootstrap-drift repair, the generated
repository's own quality gate (including `ruff check`, `ruff format --check`,
and `basedpyright`), the shared prek shims from a linked worktree, and the
final update round-trip phase (**2 passed in 40.27s**) all completed
successfully. The intermediate `fail verdict: 1 failures, 2 warnings` line is
the deliberate doctor fault-injection probe, not a regression.

The generated repository produced **zero** new or removed diagnostics under the
curated policy: the downstream gate was green before and after the migration.

## Remaining risks and portability notes

- Removing `venvPath`/`venv` relies on BasedPyright's automatic detection of
  `./.venv`. The CLI path is proven by `just validate`; the VS Code language
  server path is covered by `template/.vscode/settings.json`
  (`basedpyright.importStrategy = "fromEnvironment"`) but was not exercised
  interactively here.
- No argument-count ceiling remains anywhere: `max-args` is gone and the
  architecture guard only enforces module, function, and class line ceilings.
  This is the intended trade — parameter-object churn was judged worse than a
  wide signature — but it is a real loosening and is recorded as such.
- The Ruff floor stays at `0.15.21`, the last version actually validated, even
  though `0.15.22` is published.
- The root project deliberately has no development virtual environment, so
  focused pytest commands must go through `uv run --no-project`.
