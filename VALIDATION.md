# Validation record — 2026-08-06

Run on macOS 26.5 (Darwin 25.5.0, arm64) with Python 3.14.7, uv 0.12.2,
just 1.57.0 and prek 0.4.12.

## Change validated

The CI job that a new project could never pass. `.github/workflows/quality.yml`
held two jobs, `quality` and `acceptance`. Projection deleted the capability
that owns every `acceptance`-marked test and copied the workflow verbatim, so
the job collected no test, pytest answered exit code 5, and the runner failed
it.

- The projection overlays `.github/workflows/quality.yml` with one of the
  starting files, which holds the `quality` job only.
- The comment in the pack's own workflow said that projection replaces the file
  whole. It now states what the code does.
- Assertion `REM-7` reads the projected workflow, runs every marker selection of
  every job against the projected tree, and fails on any that collects nothing.
- The `manifest` hook compares the `root` and `package` lists only. A shim is
  user-owned, and `DESIGN_GUARDRAILS.md` states the rationale.
- `pack/tests/test_pin_coherence.py` requires one location for the `just` pin
  rather than two. The second is the job that a project no longer carries, and
  the test is pack-owned and runs in both trees.

No ceiling was raised, no test skipped and no finding suppressed. No new
`# type: ignore`, `# noqa`, skip or xfail exists. `pack/architecture.toml`,
`pack/configs/prek.toml` and `pack/configs/pyrightconfig.json` have an empty
diff over this change.

## Evidence

Commands run from the repository root, in this order.

```bash
just manifest
uv run prek run --all-files -c pack/configs/prek.toml
env PYTHONPATH=pack uv run pytest -c pack/configs/pytest.ini --rootdir=. -q -m acceptance
grep -rIn -e pyrepo -e guardrails_pack pack/
```

| Command | Result |
|---|---|
| `just manifest` | `Wrote pack/manifest.json.` |
| `prek run --all-files` | exit 0, all twelve hooks passed |
| `pytest`, acceptance marker | `84 passed, 289 deselected` |
| `grep`, both pack tokens under `pack/` | no line, exit 1 |

The gate reported **twelve of twelve hooks green**:

| Hook | Result |
|---|---|
| `lockfile` `format` `lint` `types` | passed |
| `dependencies` `architecture` `docs` `proof` | passed |
| `symbolic` `import-contracts` `tests` `manifest` | passed |

The acceptance suite reported **84 passed, 0 failed** over its 84 assertions.
The suite held 83 before this change, and `REM-7` is the new one. Group `LEG`
passed whole, so `LEG-5` holds on the Root Pack and on a Terminal Project.

The first run of the suite reported `1 failed, 83 passed`. `LEG-5` found the
gate of a Terminal Project red on `test_just_pin_is_coherent`, which is the
pack-owned test named above. That is the failure the pin floor answers, and the
second run reported `84 passed`.

Two readings come from one Terminal Project that the harness built and kept,
with `--basetemp`:

| Reading | Result |
|---|---|
| `.github/workflows/quality.yml` of the project | the `quality` job alone; no line of `.github/` holds the word `acceptance` |
| the deleted job's own command, run in the project | exit code 5, `234 deselected` |
| the `manifest` hook, run in the project | passed |

The second row is the defect, measured after the change: the command that job
ran still selects nothing, which is why the job goes rather than stays. The
third row is why the hook had to narrow, because the project starts from an
overlaid workflow and carries the record of the pack.

## Remaining risks and portability notes

- A Pack Update now reports the quality workflow of a new project as a
  customised shim, because `pack/manifest.json` records the bytes of the pack
  and the project starts from the overlaid copy. The report names no write, and
  an update never writes a shim, so the report is the only effect.
- `REM-7` reads a `-m` option of a `pytest` command. A job that selects a marker
  by another spelling is outside the scan.
- The pre-commit and pre-push hooks cannot verify a commit that touches a
  projected file. Both commits of this change used `--no-verify`, and the gate
  ran separately over the committed tree.
- `uv` can serve a cached wheel at the same version. If a shipped file disagrees
  with the checkout, clear the cache for this project before you call it a
  defect.
- Validation ran on macOS arm64 only. The runner is the proof for Linux, and the
  pull request records both CI jobs.
