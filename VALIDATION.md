# Validation record — 2026-07-15

Validated on macOS in the repository worktree with Python 3.14.6, uv,
just 1.56.0, bun 1.3.9, and git 2.55.0.

## Change validated

The retired observability backend has been removed from both product surfaces:
the benchmark no longer contains a local service stack, coding-agent hook,
post-run exporter, credentials/configuration, integration test, or operator
recipes; generated repositories no longer ship the session-capture plugins,
operator CLI, private credential examples, transcript analysis workflow, ADR,
exception ledger entry, recipes, or agent-contract guidance introduced by the
previous template change.

Removing the downstream transcript-evidence requirement is intentional: its
only capture and export path has been deleted, so leaving the requirement in
place would direct agents to an unavailable workflow. The replacement solution
must establish its own actionable evidence contract before restoring an
equivalent guardrail.

The associated root, benchmark, generated-repository, changelog, mapping, and
validation documentation has been synchronized. The earlier `CLAUDE.md`
import of `AGENTS.md` remains unchanged because it is independent of the
retired backend.

## Commands and results

- Focused regression run:
  `uv run --no-project --python 3.14 --with pytest==9.1.1 --with
  copier==9.17.0 --with grimp==3.15 pytest -q
  tests/test_benchmark_config.py tests/test_benchmark_pipeline.py
  tests/test_instantiate.py` — passed, 126 tests in 44.68s; 19 expected
  `DirtyLocalWarning` instances reported the uncommitted template changes.
- `git diff --check` — passed with no output.
- Repository-wide tracked-source search for the retired backend, its agent
  workflow identifiers, and credential variables — no matches.
- `just validate` — passed.
  - Pack tests: 205 passed in 69.72s; 20 expected `DirtyLocalWarning`
    instances reported the uncommitted template changes.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated repository full quality gate: passed.
  - Offline Copier update round trip: 1 passed in 13.88s.

## Tests removed or updated

- Removed the backend-specific unit, integration, local-stack, hook, exporter,
  credential, transcript, and installer tests together with their production
  code.
- Updated benchmark configuration and orchestration tests so they cover only
  the remaining benchmark contract.
- Updated deterministic generation expectations and the generated file-tree
  digest after removing the downstream workflow.

## Generated repository gate

- Ruff format: 40 files already formatted; lint passed.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- Architecture and documentation guards: passed.
- Import Linter: 2 contracts kept, 0 broken.
- Derived diagram sync and LikeC4 validation: passed.
- Tests: 23 passed in 1.41s.
- Branch-aware coverage: 93.30%, above the 90% floor.

## Remaining portability notes

- The first full validation on a machine may need network access to warm the
  pinned Python and LikeC4 caches. The update round-trip gate then runs with uv
  offline and package-manager network proxies pointed at an unreachable local
  endpoint.
- Real benchmark runs still require a compatible `headless_llm` checkout and
  authenticated provider CLIs; deterministic fake-agent tests do not exercise
  a live provider.
