# Validation record

Last executed: 2026-07-15 on macOS 26.5 arm64 with CPython 3.14.6, uv 0.11.28,
just 1.56.0, bun 1.3.9, and git 2.55.0.

## Change validated

Generated repositories now ship an explicit, opt-in Langfuse workflow for
complete Codex and Claude Code session tracing. The installer reads one shared
Langfuse project from the environment, checks out both official integrations at
reviewed Git commits, raises their per-field capture ceiling, and stores secrets
only in ignored mode-`0600` files written through exclusive atomic temporary
files. Codex runs the pinned entrypoint through a project `Stop` hook without
mutating global plugin state. Claude Code uses local plugin scope, captures skill
instructions, and may reuse—but never claim or remove—an already registered
global marketplace only when its source is exactly the reviewed clean revision.

Readiness verifies credentials, capture policy, hook configuration, exact clean
source revisions, and the byte-for-byte tracked inventory of Claude Code's
installed cache. It rejects modified, missing, unexpected, or symlinked cache
content. Disable first removes local credentials and hook opt-ins, then checks
external Claude cleanup. If Claude is missing or uninstall fails, the operation
returns an error while retaining ownership state and reviewed checkouts for a
safe retry; unrelated hooks, settings, and reused global marketplaces survive.

The operator can page through recent Langfuse traces, filter Codex repository
roots and Claude working directories to the generated repository, export a
complete session with observations to private JSON, and analyze a recent corpus.
Recurring diagnostics count occurrences, traces, and distinct sessions, so
repeated `E501` output in one turn cannot masquerade as cross-session friction.
The guide and ADR define the privacy boundary and the evidence loop from traced
friction to prompt, workflow, fixer, gate, architecture, or template changes.

Ruff's S606, S603, and S310 exclusions remain narrowly scoped to the generated
Codex process replacement, shell-free plugin subprocess boundary, and validated
Langfuse HTTP client. `DESIGN_MASTERY_MAPPING.md` and the generated architecture
exception ledger record the risks, controls, and removal criteria. The root
`.gitignore` now also excludes Smithers control-plane state, preventing Copier's
dirty-template commit from importing hundreds of megabytes of ignored local
runtime data into temporary clones.

## Commands and results

- `just validate`: passed.
  - Pack tests: 239 passed in 81.49s with 24 `DirtyLocalWarning` instances for
    the intentionally uncommitted template changes under validation.
  - Template cleanliness: no excluded runtime artifacts under `template/`.
  - Fresh `orchard-billing` generation: no unrendered Jinja syntax or stray
    `.jinja` suffix survived.
  - Generated repository full quality gate: passed.
  - Offline Copier update round trip: 1 passed in 13.55s.
- `uv run --no-project --python 3.14 --with pytest==9.1.1 --with
  copier==9.17.0 --with grimp==3.15 pytest -q
  tests/test_agent_observability.py
  tests/test_instantiate.py::test_default_generation_matches_recorded_output`:
  the 18 observability tests passed; the deterministic-tree assertion reported
  the expected new digest, which was then recorded and passed in `just validate`.
- `EXPECTED_GENERATED_TREE_SHA256` is
  `e91847a3df494514a2807c154a1fce5d8ee0b76752f7a353e55390766dbbfd03`.

## Tests added or updated

- Fake Codex, Claude Code, Node, and Git CLIs prove exact pinned checkouts,
  project-root Codex execution and stdin forwarding, local Claude installation,
  global marketplace reuse/ownership, and the absence of global Codex mutation.
- Installation and status tests prove secrets never enter output or argv,
  private file modes, validated capture limits, both-agent preflight, coherent
  shared-project credentials, clean source revisions, and exact installed-cache
  content including rejection of unexpected files.
- Failure and disable tests prove partial installs remain reversible, unmanaged
  local state is never seized, local secrets are scrubbed immediately, external
  cleanup failures remain actionable and retryable, and unrelated settings and
  hooks survive.
- Local HTTP servers prove Basic authentication, complete pagination, repository
  filtering, full trace/observation export, private outputs, and recurring
  diagnostic counts across distinct sessions.
- Generator contracts assert every script, recipe, ignored secret path,
  documentation registration, ADR, feedback-loop guide, and deterministic
  generated tree.

## Generated repository gate

- Ruff format: 47 files already formatted; lint passed.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- Architecture and documentation guards: passed.
- Import Linter: 2 contracts kept, 0 broken.
- Derived diagram sync and LikeC4 validation: passed.
- Tests: 23 passed in 1.98s.
- Branch-aware coverage: 93.30%, above the 90% floor.

## Remaining portability notes

- Validation uses simulated plugin CLIs and local Langfuse-compatible HTTP
  endpoints; it does not execute a real Codex project hook, mutate a real Claude
  plugin installation, or send a live provider session to Langfuse.
- Codex requires a human to review and trust the generated project hook through
  `/hooks`. Status verifies the file and pinned checkout but cannot read the
  interactive trust decision.
- The capture ceiling is 2,147,483,647 characters per field. Large tool output
  can create expensive traces, while Langfuse or a reverse proxy may enforce a
  smaller payload or storage limit.
- Codex requires version 0.128 or newer and Node.js 22 or newer; Claude Code
  requires version 2 or newer. Installation also needs Git and network access.
- The first full validation may need network access for Python and LikeC4 caches;
  the final Copier update round trip then runs offline.
