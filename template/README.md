# __PROJECT_NAME__

Python 3.14 application repository with an executable architecture and
quality contract.

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

The example separates the replaceable `Item` slice from the foundation
bricks you keep and imitate. The single owner of that distinction is the
"Foundation bricks" section of `AGENTS.md`; the decision behind it is
`docs/adr/0002-foundation-ports-and-reference-adapters.md`.

## Architecture diagrams

Diagrams are **derived from the code**, never hand-maintained
(see `docs/adr/0001-derived-architecture-diagrams.md`):

- `docs/architecture/likec4/generated/` — model and baseline views,
  regenerated from the import graph. **Never edit these by hand**; the
  quality gate fails on drift and `just fix` resolves it.
- `docs/architecture/likec4/views.c4` — team-owned free-form views; add your
  own narration here. `specification.c4` is written once.

## Documentation

`docs/README.md` is the documentation map: one row per document, saying who
reads it, when, and how its freshness is guaranteed. Read `AGENTS.md` before
changing code; record decisions under `docs/adr/`.
