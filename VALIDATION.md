# Validation record — 2026-08-06

Run on macOS 26.5 (Darwin 25.5.0, arm64) with Python 3.14.6, uv 0.12.1,
just 1.57.0 and prek 0.4.12.

## Change validated

The type and architecture backlog that the one-tree collapse exposed in nine
`pack/tests/` modules. The old root excluded that tree from analysis, so those
files reached the downstream policy for the first time.

- 88 `reportUnusedCallResult` warnings bind to `_`, the idiom the tree uses.
- 32 `reportImplicitStringConcatenation` warnings become one triple-quoted
  fixture each.
- Two `reportAny` warnings state the type of a decoded JSON document.
- The three CrossHair budget constants of `pack/tests/test_crosshair_gate.py`
  are tuples, so `ARCH026` holds.
- The two helpers of `pack/tests/test_docs_guard.py` take a `pathlib.Path`, and
  the caller builds the path, so `ARCH028` holds.
- `pack/tests/test_proof_guard.py` held 1149 lines against the 500-line ceiling
  for a test module. Its fixture trees move to `pack/tests/proof_tree.py`, and
  its cases split into four modules by subject. The ceiling is unchanged.
- The `README.md` that a projection overlays named a test directory as inline
  code, and a fresh project holds no such directory. `DOC001` failed the `docs`
  hook of every Terminal Project, and `pack/tests/test_docs_guard.py` failed its
  `tests` hook with the same finding.

No ceiling was raised, no rule removed, no exemption added and no finding
suppressed. `pack/architecture.toml`, `pack/configs/pyrightconfig.json` and
`pack/scripts/architecture_rules.py` have an empty diff over this change.

## Evidence

Commands run from the repository root, in this order.

```bash
uv run basedpyright --project pack/configs/pyrightconfig.json
env PYTHONPATH=pack uv run python -m scripts.architecture_guard
env PYTHONPATH=pack uv run pytest -c pack/configs/pytest.ini --rootdir=. -q -m "not acceptance and not session_e2e"
uv run prek run --all-files -c pack/configs/prek.toml
env PYTHONPATH=pack uv run pytest -c pack/configs/pytest.ini --rootdir=. -q -m acceptance
```

| Command | Result |
|---|---|
| `basedpyright` | `0 errors, 0 warnings, 0 notes` |
| the architecture guard | `Architecture guard passed.` |
| `pytest`, gate marker set | `284 passed, 86 deselected` |
| `prek run --all-files` | exit 0, all twelve hooks passed |

The gate reported **twelve of twelve hooks green**:

| Hook | Result |
|---|---|
| `lockfile` `format` `lint` `types` | passed |
| `dependencies` `architecture` `docs` `proof` | passed |
| `symbolic` `import-contracts` `tests` `manifest` | passed |

The acceptance suite reported **83 passed, 0 failed** over its 83 assertions.
Group `LEG` passed whole, so `LEG-5` holds on the Root Pack and on a Terminal
Project. That assertion is the definition of a green gate in both trees.

## Correction to the earlier record of this change

The earlier record stated that two assertions stay red, `REM-2` and `TER-4`. That
statement is withdrawn.

Those two failures came from a defective base, not from this change. Two commits
of the previous change never reached the remote, so this branch started from a
tree that was missing them. The recovered commits are `5a22e40`, which reads
every word search from the git index, and `be501f3`, which answers a refusal
before the projection source is read.

Both commits are merged into this branch, and both assertions now pass. The
whole acceptance suite is green.

## Remaining risks and portability notes

- The pre-commit hook runs the gate against the staged tree while `HEAD` is
  still the parent commit. Several capability tests compare the tree with the
  record of `HEAD`, so the hook fails on any commit that changes a projected
  file. The gate passes on the committed tree, which CI runs.
- `uv` can serve a cached wheel at the same version. If a shipped file disagrees
  with the checkout, clear the cache for this project before you call it a
  defect.
- Validation ran on macOS arm64 only.
