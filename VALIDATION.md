# Validation record — 2026-08-05

Run on macOS 26.5 (Darwin 25.5.0, arm64) with Python 3.14.6, uv 0.12.0,
just 1.57.0 and prek 0.4.12.

## Change validated

The last ticket of the one-tree refactor: every document rewritten against the
vocabulary of `CONTEXT.md`, the two word searches of the acceptance suite
settled, and the temporary handover directory deleted.

- `AGENTS.md` is one contract for one tree. The section that split it into a
  maintainer contract and a downstream contract is deleted.
- `README.md`, `CHANGELOG.md`, `DESIGN_GUARDRAILS.md`, `docs/README.md`, the
  ADRs and `pack/docs/architecture/` describe the tree that exists.
- ADR-0002 and ADR-0004 return as superseded records, so the ADR numbers are
  contiguous again. ADR-0007 becomes superseded, and ADR-0008 records the two
  ownership surfaces that replaced its four classes.
- The prose word search now reads its terms from the `_Avoid_` lines of
  `CONTEXT.md`, so the vocabulary and the ban list are one fact.
- Two identifiers leave the identifier word search, with the reasoning in
  `DESIGN_GUARDRAILS.md`. Each named a file that the deletion boundary keeps.

## Evidence

Commands run from the repository root, in this order.

```bash
PYTHONPATH=pack uv run python -m scripts.manifest_guard --write
uv run prek run --all-files -c pack/configs/prek.toml
```

The gate reported **ten of twelve hooks green**:

| Hook | Result |
|---|---|
| `lockfile` `format` `lint` `dependencies` | passed |
| `docs` `proof` `symbolic` `import-contracts` | passed |
| `tests` `manifest` | passed |
| `types` | **failed**, 0 errors and 122 warnings |
| `architecture` | **failed**, 6 violations |

The `tests` hook reported **284 passed, 86 deselected** in 52.85 seconds. The
`docs` hook reported `Documentation guard passed.` after 64 findings before the
change.

Both word searches of the acceptance suite print nothing over this tree, with
the stated exemptions only.

## Remaining risks and portability notes

- **`types` and `architecture` are red, and this change did not cause it.** The
  counts are the same before and after: 122 warnings and 6 violations, on nine
  files of `pack/tests/` that the one-tree refactor moved. 88 warnings are an
  unused call result, 32 are an implicit string concatenation, three violations
  are a mutable module constant, two are a `str` parameter that names a path,
  and one is a 1149-line module against a 500-line ceiling. A separate ticket
  owns that debt. No rule was weakened to hide it.
- **The gate is therefore still red, and two consequences follow.** `just setup`
  ends with the gate, so `init` still stops before its first commit and reports
  exit 4. The acceptance suite still commits such a tree itself. Both become
  unnecessary when the debt ticket lands, and neither needs a change here.
- **The 53 acceptance assertions were not run for this record.** They need a
  built wheel, a throwaway tool install and two projections, and assertion
  `LEG-5` reads the gate outcome that the row above already reports. The two
  word searches were run directly against this tree instead.
- Validation ran on macOS arm64 only.
