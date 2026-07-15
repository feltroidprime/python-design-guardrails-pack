# Validation record

Last executed: 2026-07-15 on macOS 26.5 arm64 with CPython 3.14.6, uv 0.11.28,
just 1.56.0, bun 1.3.9, and git 2.55.0.

## Change validated

Generated repositories now ship `CLAUDE.md` containing `@AGENTS.md` whenever
`agents_contract != "none"`. Claude Code reads `CLAUDE.md` and never
`AGENTS.md`, so the operating contract only reached it when a prompt happened
to tell the agent to open the file. The import loads the contract in every
session while `AGENTS.md` remains its single owner, and the conditional path
keeps both files absent under `agents_contract = "none"`.

Admitting a second root document required the documentation map to be rendered
rather than copied verbatim, which exposed and fixed a pre-existing defect: the
`agents_contract = "none"` variant generated a repository whose own `docs guard`
failed with two DOC001 violations, because the copied map still linked to the
`AGENTS.md` the variant had removed. No campaign had run that ablation, and
`validate_pack.py` only generates the default answers, so nothing had caught it.
The map's `AGENTS.md` and `CLAUDE.md` rows are now conditional.

No guardrail was added, removed, or weakened, so `DESIGN_MASTERY_MAPPING.md` is
unchanged.

## Commands and results

- Both variants' `docs guard`, run directly against freshly generated
  repositories: the `agents_contract = "none"` variant reported
  `docs/README.md:27` and `docs/README.md:39` DOC001 violations before the fix
  and `Documentation guard passed.` (exit 0) after it; the default variant
  passes with `CLAUDE.md` present.
- `just test`: passed; 220 passed in 108.27s. The 24 `DirtyLocalWarning`
  instances reflect the uncommitted template changes under validation.
- `just validate`: passed.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived, including the newly rendered documentation map.
  - Generated quality gate: all steps passed.
  - Offline update round trip: 1 passed in 14.95s.
- `EXPECTED_GENERATED_TREE_SHA256` was recomputed from a fresh 66-file
  generation rather than copied from a failure message.

## Generated repository gate

- Ruff format and lint: passed.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- Architecture and documentation guards: passed.
- Import Linter: 2 contracts kept, 0 broken.
- Derived diagram sync and LikeC4 validation: passed.
- Tests: 23 passed in 1.31s.
- Branch-aware coverage: 93.30%, above the 90% floor.

## Remaining portability notes

- The import is not free. `AGENTS.md` is roughly 400 lines, about twice the size
  Claude Code's own documentation recommends per instruction file, and it now
  enters context in every session of a generated repository. Splitting the
  contract into path-scoped `.claude/rules/` files is the only mechanism that
  would reduce that cost, and it is Claude-specific; measure it as an experiment
  before adopting it.
- `benchmarks/config/prompts/build_charter.md` already instructs builder agents
  to read `AGENTS.md`, so benchmark arms were never affected by the gap this
  change closes. The guardrails arm now loads the contract twice per build
  session: once by import, once by the charter's instruction. Registry rows from
  campaigns pinned to earlier template refs remain comparable among themselves.
- The first full validation on a machine may need network access to warm the
  pinned Python and LikeC4 caches. The update round-trip gate then runs with uv
  offline and package-manager network proxies pointed at an unreachable local
  endpoint.
- Real benchmark runs still require a compatible `headless_llm` checkout and
  authenticated provider CLIs; the deterministic fake-agent and reference
  implementation tests do not exercise a live provider.
