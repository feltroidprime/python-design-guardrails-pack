# Python Design Guardrails Pack

A reusable Python 3.14 repository template that turns software-design principles into executable constraints for humans and coding agents.

## Two ways to be here

- **Using the pack**: run `instantiate.py` to create a new repository, then work inside that repository under its own `AGENTS.md`, justfile, and quality gate. See "Create a new repository" below.
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
- a single local quality gate mirrored in CI.

## Create a new repository

```bash
python3 instantiate.py my-product my_product ../my-product
cd ../my-product
uv sync --all-groups
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run python scripts/quality_gate.py
```

Arguments:

1. distribution/project name, such as `my-product`;
2. import package, such as `my_product`;
3. output directory.

The generated project intentionally contains a tiny vertical slice that passes the architecture and demonstrates value objects, a use case, ports, an outbound adapter, an inbound adapter, and a composition root. Delete or replace the example after preserving the structure.

## Key files in a generated repository

- `AGENTS.md`: operational contract for coding agents.
- `architecture.toml`: deterministic architecture policy.
- `scripts/architecture_guard.py`: AST-level fitness functions.
- `pyproject.toml`: Ruff, BasedPyright, pytest, Coverage, Import Linter, and dependencies.
- `.pre-commit-config.yaml`: fast commit checks and full pre-push gate.
- `.vscode/settings.json`: hides derived artifacts (caches, coverage, `.venv`) from the VS Code explorer and search.
- `docs/architecture/`: pattern admission rules, ADRs, migration and exception templates.
- `scripts/quality_gate.py`: canonical one-command acceptance gate.

See `DESIGN_MASTERY_MAPPING.md` for the detailed mapping from curriculum promises to repository mechanisms.

## Maintaining the pack

Prerequisites: `python3` (3.14), [`uv`](https://docs.astral.sh/uv/), and [`just`](https://github.com/casey/just). The root intentionally has no `pyproject.toml` or virtualenv; pytest is supplied ephemerally by `uv run --with`.

```bash
just test       # generator unit tests (fast inner loop)
just validate   # canonical validation — required before claiming any template change done
```

`just validate` runs the generator tests, then instantiates a throwaway repository in a temporary directory, verifies that `template/` carries no local runtime artifacts, that no placeholder token survives generation, resolves the pinned dependencies, and runs the generated repository's own full quality gate before cleaning up. The last executed validation is recorded in `VALIDATION.md`.
