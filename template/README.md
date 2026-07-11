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

## Architecture diagrams

Diagrams are **derived from the code**, never hand-maintained
(see `docs/adr/0001-derived-architecture-diagrams.md`):

- `docs/architecture/likec4/generated/` — model and baseline views,
  regenerated from the import graph. **Never edit these by hand**; the
  quality gate fails on drift and `just fix` resolves it.
- `docs/architecture/likec4/views.c4` — team-owned free-form views; add your
  own narration here. `specification.c4` is written once.

Read `AGENTS.md` before changing code. Architecture decisions live under `docs/adr/`.
