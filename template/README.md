# __PROJECT_NAME__

Python 3.14 project generated from the Python Design Guardrails Pack.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) — Python toolchain and dependencies.
- [`just`](https://github.com/casey/just) — command runner.
- [`bun`](https://bun.sh) — runs the pinned LikeC4 CLI via `bunx` for the
  architecture diagrams. No JavaScript project files live in this
  repository; the first `bunx` invocation downloads the pinned package once,
  then uses the cache.

## Bootstrap

```bash
uv sync --all-groups
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run python scripts/quality_gate.py
```

## Daily commands

```bash
just fix        # deterministic auto-fixes, including diagram regeneration
just check      # full local acceptance gate
just test       # tests only
just arch       # architecture fitness functions only
just diagrams   # browse live architecture diagrams (LikeC4 viewer)
just update     # update dependencies and hook revisions intentionally
```

## Try the example application

```bash
uv run python -m __PACKAGE__ add "First item"   # persists to ./items.db
uv run python -m __PACKAGE__ list
```

## What to replace, what to keep

The example separates throwaway from foundation (see
`docs/adr/0002-foundation-ports-and-reference-adapters.md`):

- **Replace**: the `Item` aggregate, its value objects, use cases, and CLI
  verbs — they exist to be substituted by your real domain.
- **Keep**: the foundation bricks, each the reference exemplar of a
  cross-cutting capability you will need again — the `Clock` and
  `ItemIdFactory` callable ports, the `EventPublisher` protocol with its
  in-process implementation and audit-log consumer, the SQLite reference
  adapter (error translation + context-managed lifecycle), the reusable
  repository contract test in `tests/contract/`, and the `python -m`
  entry point through the single composition root.

The "Foundation bricks" table in `AGENTS.md` maps each recurring need to
the brick to imitate.

## Architecture diagrams

Diagrams are **derived from the code**, never hand-maintained
(see `docs/adr/0001-derived-architecture-diagrams.md`):

- `docs/architecture/likec4/generated/` — model and baseline views,
  regenerated from the import graph. **Never edit these by hand**; the
  quality gate fails on drift and `just fix` resolves it.
- `docs/architecture/likec4/views.c4` — team-owned free-form views; add your
  own narration here. `specification.c4` is written once.

Read `AGENTS.md` before changing code. Architecture decisions live under `docs/adr/`.
