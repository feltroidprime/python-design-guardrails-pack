# Validation record — 2026-08-06

Run on macOS 26.5 (Darwin 25.5.0, arm64) with Python 3.14.6, uv 0.12.2,
just 1.57.0 and prek 0.4.12.

## Change validated

The toolchain gap that made both CI jobs red on Linux. The `tests` hook runs
`just` against a fixture tree, in `pack/tests/test_release.py`. The pack-owned
composite action provisioned `uv` and Python 3.14 and nothing else.

- `pack/ci/action.yml` installs `just 1.57.0` through `uv` and its PyPI
  distribution `rust-just`, and adds the tool directory to `GITHUB_PATH`.
- The `acceptance` job of `.github/workflows/quality.yml` repeats that step. The
  job does not call the composite action, and `LEG-5` runs the same gate.
- `pack/tests/test_pin_coherence.py` registers the pin as a two-location pin, so
  the two copies cannot drift apart.

No ceiling was raised, no rule removed, no test skipped and no finding
suppressed. `pack/architecture.toml`, `pack/configs/prek.toml` and
`pack/configs/pyrightconfig.json` have an empty diff over this change.

## Evidence

Commands run from the repository root, in this order.

```bash
just manifest
uv run prek run --all-files -c pack/configs/prek.toml
env PYTHONPATH=pack uv run pytest -c pack/configs/pytest.ini --rootdir=. -q -m acceptance
```

| Command | Result |
|---|---|
| `just manifest` | `Wrote pack/manifest.json.` |
| `prek run --all-files` | exit 0, all twelve hooks passed |
| `pytest`, acceptance marker | `83 passed, 288 deselected` |

The gate reported **twelve of twelve hooks green**:

| Hook | Result |
|---|---|
| `lockfile` `format` `lint` `types` | passed |
| `dependencies` `architecture` `docs` `proof` | passed |
| `symbolic` `import-contracts` `tests` `manifest` | passed |

The acceptance suite reported **83 passed, 0 failed** over its 83 assertions.
Group `LEG` passed whole, so `LEG-5` holds on the Root Pack and on a Terminal
Project.

## Remaining risks and portability notes

- macOS carries `just` already, so this defect is invisible here. The runner is
  the only proof, and the pull request records both CI jobs.
- The pin now exists in two files. `pack/tests/test_pin_coherence.py` is the one
  mechanism that keeps them equal.
- The pre-commit hook runs the gate against the staged tree while `HEAD` is
  still the parent commit. Several capability tests compare the tree with the
  record of `HEAD`, so the hook fails on any commit that changes a projected
  file. The gate passes on the committed tree, which CI runs.
- `uv` can serve a cached wheel at the same version. If a shipped file disagrees
  with the checkout, clear the cache for this project before you call it a
  defect.
- Validation ran on macOS arm64 only.
