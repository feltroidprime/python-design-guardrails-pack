# __PROJECT_NAME__

Python 3.14 project generated from the Python Design Guardrails Pack.

## Bootstrap

```bash
uv sync --all-groups
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run python scripts/quality_gate.py
```

## Daily commands

```bash
just fix        # deterministic auto-fixes
just check      # full local acceptance gate
just test       # tests only
just arch       # architecture fitness functions only
just update     # update dependencies and hook revisions intentionally
```

Read `AGENTS.md` before changing code. Architecture decisions live under `docs/adr/`.
