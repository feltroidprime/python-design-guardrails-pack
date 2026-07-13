# Python Design Guardrails Pack

A reusable Python 3.14 repository template that turns software-design principles into executable constraints for humans and coding agents.

## Two ways to be here

- **Using the pack**: run `python-repo init` (or `instantiate.py` directly) to create a new repository, then work inside that repository under its own `AGENTS.md`, justfile, and quality gate. See "Create a new repository" below.
- **Maintaining the pack**: this repository is a meta-repository; `template/` is the canonical source copied into every generated repository and `instantiate.py` is the generator. Read the root `AGENTS.md` before changing anything — `template/AGENTS.md` is downstream content, not the contract for working here.

This pack is inspired by the public curriculum of ArjanCodes' **Software Design Mastery** program, but it is an independent implementation. The course is still presented publicly as a 2026 waitlist; this repository therefore separates:

- what the public curriculum states explicitly;
- what is inferred from ArjanCodes' established Python teaching;
- the concrete guardrails designed in this pack.

## What is enforced

### Core Designer — always on

- strict Python 3.14 typing with BasedPyright;
- no explicit `Any`, blanket ignores, wildcard imports, generic dumping-ground modules, or hidden dependencies;
- cohesive size and complexity ceilings;
- immutable value objects and events in declared modules;
- fail-fast domain validation;
- deterministic tests, property tests, branch coverage, and disabled network access.

### System Designer — default architecture profile

- inward dependency direction: `bootstrap -> adapters -> application -> domain`;
- independent inbound and outbound adapters;
- pure synchronous domain logic;
- I/O, concurrency, wall-clock time, randomness, UUID generation, and frameworks kept outside the domain;
- explicit `Protocol` ports and constructor injection;
- one composition root.

### Master Designer — decision discipline

- ADR required for architecture exceptions, new cross-layer dependencies, framework adoption, or migration strategies;
- exception ledger with expiry/removal criteria;
- Strangler and Branch-by-Abstraction migration templates;
- a single local quality gate mirrored in CI;
- architecture diagrams derived from the import graph (LikeC4 + grimp): the gate fails when the committed model lags the code or a hand-written view references a missing element, so stale diagrams are uncommittable.

## Install the generator system-wide (once)

```bash
just install    # runs: uv tool install --force --editable .
```

This puts a `python-repo` command on your PATH (via `~/.local/bin`). The
install is editable, so template changes and `git pull` in this repository
take effect immediately without reinstalling.

## Create a new repository

```bash
python-repo init my-product .        # creates ./my-product, package my_product
cd my-product
uv sync --all-groups
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run python scripts/quality_gate.py
```

`python-repo init <name> [directory] [--package NAME] [--public] [--no-github] [--no-git]`:

1. `name`: distribution/project name, such as `my-product`;
2. `directory`: parent directory; the repository is created at
   `<directory>/<name>` (default: current directory);
3. `--package`: import package name; by default it is derived from the
   project name (`my-product` → `my_product`).

After generating the files, `init` also initializes version control:

- `git init` on branch `main` plus an initial commit;
- `gh repo create <name> --private --source . --remote origin --push` — a
  **private** GitHub repository by default (requires an authenticated
  [GitHub CLI](https://cli.github.com/); run `gh auth login` once).

Flags: `--public` creates the GitHub repository public instead; `--no-github`
keeps the repository local-only (git still initialized); `--no-git` skips
version control entirely. If `gh` is missing or fails, the local repository
is kept and the exact `gh repo create` command to run later is printed
(missing `gh` exits 0; a failed `gh` exits 1).

Without installing anything, the legacy positional form still works and is
purely local (no git, no GitHub):

```bash
python3 instantiate.py my-product my_product ../my-product
```

The generated project contains a small vertical slice built on **foundation bricks**: a replaceable example domain (`Item`) wired through keep-me exemplars of every cross-cutting capability — an injected clock and id factory, a typed in-process event publisher with an audit-log consumer, a SQLite reference adapter demonstrating error translation and context-managed lifecycle, a reusable repository contract-test kit, and a runnable `python -m` CLI through the single composition root. Replace the `Item` domain; keep the bricks (rationale: the generated `docs/adr/0002-foundation-ports-and-reference-adapters.md`).

## Key files in a generated repository

- `AGENTS.md`: operational contract for coding agents.
- `architecture.toml`: deterministic architecture policy.
- `scripts/architecture_guard.py`: AST-level fitness functions.
- `pyproject.toml`: Ruff, BasedPyright, pytest, Coverage, Import Linter, and dependencies.
- `.pre-commit-config.yaml`: fast commit checks and full pre-push gate.
- `.vscode/settings.json`: hides derived artifacts (caches, coverage, `.venv`) from the VS Code explorer and search.
- `docs/architecture/`: pattern admission rules, ADRs, migration and exception templates.
- `docs/architecture/likec4/`: architecture diagrams — `generated/` is derived from the import graph by `scripts/sync_architecture_diagrams.py` (never hand-edited), `views.c4` is team-owned narration.
- `scripts/quality_gate.py`: canonical one-command acceptance gate.

See `DESIGN_MASTERY_MAPPING.md` for the detailed mapping from curriculum promises to repository mechanisms.

## Maintaining the pack

Prerequisites: `python3` (3.14), [`uv`](https://docs.astral.sh/uv/), [`just`](https://github.com/casey/just), and [`bun`](https://bun.sh) (pack validation runs the downstream quality gate, which validates the LikeC4 diagrams through a pinned `bunx` invocation). The root `pyproject.toml` exists only to package the `python-repo` CLI (`uv tool install`); the root intentionally has no virtualenv or lock file, and pytest and grimp are supplied ephemerally by `uv run --no-project --with`.

```bash
just test       # generator unit tests (fast inner loop)
just validate   # canonical validation — required before claiming any template change done
```

`just validate` runs the generator tests, then instantiates a throwaway repository in a temporary directory, verifies that `template/` carries no local runtime artifacts, that no placeholder token survives generation, resolves the pinned dependencies, and runs the generated repository's own full quality gate before cleaning up. The last executed validation is recorded in `VALIDATION.md`.
