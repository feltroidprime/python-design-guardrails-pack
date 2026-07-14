# Validation record

Last executed: 2026-07-14, macOS 26.5 (arm64), CPython 3.14.6, uv 0.11.28,
bun 1.3.9, via `just validate` — after adding the optional local Langfuse lab:
six exactly pinned Compose services, ignored generated credentials, health and
lifecycle recipes, an authenticated recent-traces CLI, and Langfuse's Claude
Code plugin v1.0.0 pinned to commit
`3f301f3840c975bdbd16b8140140d139f27aa99b`. Seven deterministic lab tests
cover the configuration and scripts without Docker, a network, or provider
SDKs. Live acceptance on Docker 29.6.1 / Compose 5.3.1 brought all services
healthy, ingested an independent interactive Claude Code turn, retrieved its
trace through the public API, and removed every project container.

Previously, the end-to-end value benchmark (`benchmarks/`) added a maintainer
harness where one LLM (via `headless_llm`)
builds the same specified application in an empty repository and in a
template-generated repository, compared by functional probes, pinned neutral
analyzers (ruff/basedpyright/radon/coverage via `uvx`), build-effort
statistics, and a blind cross-family LLM judge panel (both presentation
orders, anti-volume rubric, no provenance in the judge framing — enforced by
a unit test). The two arms run concurrently by default (`run.parallel_arms`,
one runner per arm, proven by a barrier test), benchmark agents opt out of
the host's global MCP configuration (`mcp_servers=()`), and a rich-based
live dashboard (`benchmarks/e2e/tui.py`, `--tui`/`--no-tui`) renders the
orchestrator's structured event stream without touching what is measured.
`just benchmark [config] [model] [provider] [effort]` picks the app spec and
the coding model without editing TOML (`apply_builder_overrides`, aliases
sonnet/opus/haiku, provider switch drops claude-specific settings).
A two-pass audit (methodology + silent bugs, with live micro-probes against
the real provider CLIs) then hardened the design: generated repositories no
longer carry any pack-identifying wording (`template/README.md`,
`template/pyproject.toml` description and toolchain comment, ADR owner
lines — enforced by a bundle test against a real instantiation); judges run
tool-less where the provider allows, in a fresh neutral working directory
(their CLIs inject CWD instruction files and reveal the path); files the
builder created or modified bypass judge exclusions (git-diff against the
arm's initial commit) so agent work is never hidden; every static metric now
measures the same application scope as the judge bundle, with whole-repo LOC
reported separately; coverage runs under a generated neutral rcfile immune
to the arm's own coverage config, with tooling exit codes recorded; the
judging report declares a primary endpoint (preference of
position-consistent judges — flipped judges carry no weight), prints the
per-judge×order matrix and observed judge tool calls, and reports cached
input tokens; pytest summaries parse only the final summary line; probe
timeouts keep partial output; capture names cannot shadow `{db}`/`{ws}`;
the launcher always re-executes through uv so a stale ambient headless_llm
can never be benchmarked silently.
The harness is standard-library-only except one lazily imported
`headless_llm` adapter and the optional TUI (rich pinned in the launcher),
so the deterministic pack tests (`tests/test_benchmark_config.py`,
`tests/test_benchmark_pipeline.py`, 47 tests) run the full pipeline with
fake agents — including the fairness invariants (identical build prompt
across arms, symmetric judge exclusions, out-of-tree output root) and the
event-stream contract — without any network or SDK. Benchmark runs write
only outside the working tree. Before that: after adding the Path-discipline guards
ARCH019–ARCH020 (`scripts/path_discipline.py`, a separate module like
`none_discipline.py`) and their single source of truth, the "Path
discipline" section of the template `AGENTS.md`: a filesystem location is
`pathlib.Path` from the moment it exists; `str` paths are wire data parsed
at the adapter edge and serialized only inside the final external call.
ARCH019 rejects path-named parameters and returns that admit `str`
(including `str | Path` unions and `list[str]` elements); ARCH020 rejects
path-named annotated fields that admit `str`. Name matching is whole-token
(`profile`/`file_format` stay clean; `config_file` is a path); mapping
annotations check only the key position, so `files: dict[Path, str]` —
path-to-content, the diagram-sync exemplar — stays legal. Both codes are
`ARCH-EXCEPTION` marker-suppressible. Ruff's `PTH` family (already enabled)
keeps rejecting the `os.path` API at call sites; the guard adds the part a
call-site linter cannot see, and BasedPyright then propagates `Path`-typed
boundaries to every caller. Pack tests (`tests/test_path_discipline.py`,
11 tests) prove each rule fires on planted violations and stays silent on
legitimate idioms. Before that: after adding the documentation contract:
the documentation map (`docs/README.md`: one row per document, freshness
ladder derived > checked > dated, admission rule) and the docs guard
(`scripts/docs_guard.py`, new `docs guard` step in the quality gate and in
`just arch`) with rules DOC001–DOC007 — broken path references in markdown
(resolved against the file's directory, the repository root, and the package
root; fenced code blocks and URLs ignored), `ARCH-EXCEPTION` markers naming
nonexistent ADRs, ADR file-name/heading/front-matter/status conventions,
non-contiguous or duplicate ADR numbering, and documents not registered in
the map. The template `README.md` no longer paraphrases the foundation-bricks
distinction (single owner: `AGENTS.md`), and `AGENTS.md` gained the
"Documentation" section stating the three rules. Pack tests
(`tests/test_docs_guard.py`, 17 tests) prove each rule fires on planted
violations and stays silent on legitimate prose, and that the shipped
template passes its own documentation contract. Before that: after adding
the None-discipline guards
ARCH016–ARCH018 (`scripts/none_discipline.py`, a separate module so
`architecture_rules.py` respects its own 400-line ceiling) and their single
source of truth, the "None discipline" section of the template `AGENTS.md`.
`architecture_guard.py` became the composition point: it reads and parses
each file once, reports ARCH000 itself, runs both rule families on the same
tree, and applies the inline `ARCH-EXCEPTION: ADR-XXXX` marker centrally for
exactly the codes that admit it. Pack tests
(`tests/test_none_discipline.py`) prove each rule fires on planted
violations and stays silent on legitimate idioms (optional port returns
outside the domain, function-local optionals, non-collection edge DTO
fields). Before that: after adding `.codebase-memory/` (local
index of the codebase-memory MCP server) to the ignore set everywhere it
belongs: template `.gitignore`, template `.vscode/settings.json`
(files.exclude + watcherExclude), and `IGNORED_ARTIFACT_PATTERNS` in
`instantiate.py`; and before that after teaching `python-repo init` to run
`git init` + initial commit and `gh repo create --private … --push` by
default (flags `--public`, `--no-github`, `--no-git`; gh behavior tested
against a PATH-stubbed `gh`, never the real one), and previously after
replacing the throwaway example slice
with the foundation-bricks slice (ADR-0002): `Clock`/`EventPublisher` ports,
in-process event publisher + audit-log consumer, SQLite reference adapter
with error translation and context-managed lifecycle, reusable repository
contract-test kit, `python -m` CLI entry point; and after making `tests/`
namespace packages (no `__init__.py`, `consider_namespace_packages` +
`pythonpath = ["."]`) with two new guard rules — ARCH014 (`__init__.py`
forbidden under `tests/`) and ARCH015 (empty `__init__.py` forbidden
anywhere) — which required splitting `scripts/architecture_policy.py` out of
`architecture_rules.py` to respect the guard's own 400-line module ceiling.
Both rules were verified to fire on planted files. Keeping the `src/` layer
`__init__.py` files is deliberate: removing them was tested and breaks grimp
(subpackages vanish from the import graph), taking down both the
import-linter layers contract and the derived diagrams.

## Pack-level checks (`just validate`)

- Generator test suite (`tests/test_instantiate.py` +
  `tests/test_none_discipline.py` + `tests/test_path_discipline.py` +
  `tests/test_docs_guard.py` + `tests/test_benchmark_config.py` +
  `tests/test_benchmark_pipeline.py` + `tests/test_langfuse_lab.py`): 124 passed — name
  validation, non-empty-directory refusal, package renaming, full placeholder
  replacement, cache-artifact exclusion, expected-file preservation
  (including `__main__.py`, the SQLite adapter, `application/errors.py`,
  ADR-0002, and the contract kit), executable behavior of the generated
  architecture guard and of the example CLI slice (`add` + `list` through
  `memory_application`), the diagram sync script (fresh `--check` passes,
  planted-module drift fails and names the fix command, `--write` resolves
  it, output byte-stable across runs), and the `init` subcommand (creation
  under the directory argument, derived/explicit package names, git init
  with exactly one initial commit, private-by-default `gh repo create`
  argument contract via a stub `gh`, `--public` flip, failing `gh` keeps the
  local repo and exits 1 with the manual command, `--no-git` skip, rejection
  of underivable names, refusal of non-empty targets). Diagram sync tests
  run with grimp only — no Bun.
- Template cleanliness: no local runtime artifacts under `template/`.
- Fresh instantiation (`orchard-billing` / `orchard_billing`) in a temporary
  directory: no placeholder token survived in any file name or file content.

## Generated repository checks (its own `scripts/quality_gate.py`)

- `uv lock --check`: passed.
- Ruff formatting and linting: passed.
- BasedPyright, `pythonVersion = "3.14"`, recommended mode,
  `failOnWarnings = true`, explicit `Any` errors: 0 errors, 0 warnings.
- Repository AST architecture guard: passed.
- Documentation guard (map registration, path references, ADR conventions,
  exception markers): passed.
- Import Linter: 2 contracts kept, 0 broken (22 files, 22 dependencies).
- Diagram sync: derived LikeC4 model matches the import graph, including the
  new `application/errors` module and the bootstrap → inbound/domain.events
  relationships.
- Diagram views: `bunx likec4@1.58.0 validate` — valid.
- Tests: 23 passed with sockets disabled (contract certification of both
  repository implementations, CLI integration, SQLite lifecycle
  persistence, audit-log event delivery).
- Branch-aware coverage: 93.30%, above the 90% floor.

## Known limitations

- `application/ports.py` measures 0% covered: it is a type-only module (all
  imports of it are under `TYPE_CHECKING`), so it is never imported at
  runtime. `__main__.py` measures 0% for the same class of reason (its guard
  only fires under `python -m`). The overall floor still holds; do not "fix"
  this by weakening the coverage configuration.
- The `_decode` row-shape mismatch branch of the SQLite adapter is
  unreachable through the public API with a healthy database and stays
  uncovered by design.
- Validation runs the toolchain pinned by the template (uv-managed Python
  3.14); the first run needs network access to resolve dependencies and, once
  per machine, for `bunx` to download the pinned LikeC4 CLI.
