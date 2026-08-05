# Validation record — 2026-08-05

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

The acceptance suite reported **81 passed, 2 failed** over its 83 assertions.
Both failures also occur at commit `cb7ac14`, the parent of this change, so
neither one is a regression of it. The two are recorded below.

Group `LEG` reported **18 passed**, so `LEG-5` holds on the Root Pack and on a
Terminal Project. That assertion is the definition of a green gate in both
trees.

## Remaining risks and portability notes

- **`REM-2` reads third-party code, not project code.** The word search of
  assertion `REM-2` walks the whole projected tree, and the virtual environment
  holds every dependency that `uv sync --all-groups` installs. One of them,
  `execnet`, uses the capability word in its own source. The exemption list of
  the assertion covers `docs/vendored` and `.agents` and not the environment
  directory. The ban lists are settled, so this change does not touch them.
- **`TER-4` fails because the pack's own tests read the staged payload.** While
  a payload sits inside the import package, the payload locator prefers it over
  the checkout. Two command-surface cases of the One-shot Bootstrap capability
  then report exit 70 rather than the refusal exit 3, so an interrupted build
  turns the `tests` hook red. The correction belongs to that capability, not to
  this change.
- **Both failures pre-date this change.** Measured at `cb7ac14` in a separate
  worktree: `2 failed in 60.76s`, the same two assertions.
- The pre-commit hook runs the gate against the staged tree while `HEAD` is
  still the parent commit. Several capability tests compare the tree with the
  archive of `HEAD`, so the hook fails on any commit that changes a projected
  file. The gate passes on the committed tree, which CI runs.
- Validation ran on macOS arm64 only.
