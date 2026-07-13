# Validation record

Last executed: 2026-07-13, macOS (arm64), CPython 3.14.6, uv 0.11.28,
bun 1.3.9, via `just validate` — after adding the None-discipline guards
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
  `tests/test_none_discipline.py`): 41 passed — name
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
