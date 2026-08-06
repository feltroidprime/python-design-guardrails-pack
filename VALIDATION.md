# Validation record — 2026-08-06

Run on macOS 26.5 (Darwin 25.5.0, arm64) with Python 3.14.7, uv 0.12.2,
just 1.57.0 and prek 0.4.12.

## Change validated

A documentation audit against four readers: a human and a coding agent, each
reading the Root Pack and reading a Terminal Project. The audit found the
contract misstating its own gate, the projected documents describing a
repository their reader does not have, and the guards reporting a code without
its fix.

- `AGENTS.md` stated the capability layer order as `api`, `domain`,
  `application`, `adapters`. `pack/configs/importlinter.ini` enforces
  `api`, `adapters`, `application`, `domain`.
- `AGENTS.md` counted twelve hooks. The gate runs eleven upstream file hooks
  and then twelve local hooks.
- `AGENTS.md` said the gate never rewrites a file. Three upstream hooks repair
  a file in place.
- `AGENTS.md` said CI runs the same command. CI runs one more job, which the
  `tests` hook excludes.
- `AGENTS.md` offered the `ARCH-EXCEPTION` marker as generally available.
  `pack/scripts/architecture_guard.py` accepts it for `ARCH016` through
  `ARCH030` alone, so the marker did nothing for a structural code.
- `init` ran the gate before the first commit. Several pack tests read the
  tracked tree through git, so a new repository met eight failures on its first
  gate run. The commit now runs before `just setup`.
- The `api.py` of the One-shot Bootstrap capability carried a fenced synopsis
  that argparse fused into one paragraph, and an issue citation that reached
  the terminal of an end user.

## Evidence

Commands run from the repository root, in this order.

```bash
just manifest
just check
uv run pytest -c pack/configs/pytest.ini --rootdir=. -m acceptance
```

| Command | Result |
|---|---|
| `just manifest` | `Wrote pack/manifest.json.` |
| `just check` | exit 0, every hook passed |
| `pytest`, acceptance marker | `84 passed, 289 deselected in 398.36s` |

The gate reported **eleven upstream hooks and twelve local hooks green**:

| Hook | Result |
|---|---|
| the eleven upstream file hooks | passed |
| `lockfile` `format` `lint` `types` | passed |
| `dependencies` `architecture` `docs` `proof` | passed |
| `symbolic` `import-contracts` `tests` `manifest` | passed |

The acceptance suite reported **84 passed, 0 failed**. The suite defines 54
distinct assertion identifiers, and pytest collected 84 parametrized tests from
them.

Two earlier runs of the acceptance suite failed, and both failures were real.
`REM-2` found the capability word in `AGENTS.md`, which projection copies
verbatim, so the word reached every Terminal Project. `PAR-7` found a bytecode
file inside the starting files, written by a `pytest` run that did not set
`PYTHONPYCACHEPREFIX`. The record above is the run that followed both repairs.

One Terminal Project was built and kept, to measure the `init` order:

| Reading | Result |
|---|---|
| tracked files after `init` | 533 |
| commits after `init` | one, `Initial commit of fresh-widget` |
| the gate, run by `just setup` inside that project | every hook passed |

The second and third rows are the change: before it, the same reading gave zero
tracked files, no commit, and eight failures from tests that read the tracked
tree.

## Remaining risks and portability notes

- A Pack Update reports the quality workflow of a new project as a customised
  shim, because `pack/manifest.json` records the bytes of the pack and the
  project starts from the overlaid copy. The report names no write, and an
  update never writes a shim, so the report is the only effect.
- If a commit touches a projected file, the pre-commit and pre-push hooks
  cannot check it. Only then is `--no-verify` legal, and a full gate run over
  the committed tree must follow it. Neither commit of this change needed it,
  and both ran the whole gate through the hooks.
- Every recipe writes its bytecode cache under `.venv/pycache`. A recipe that
  runs before the environment exists leaves `.venv/` holding that directory
  alone. `uv sync` then refuses, and `uv venv` repairs neither with `--clear`
  nor with `--force`. Delete `.venv/` and run `just setup` again.
- A `pytest` run that does not set `PYTHONPYCACHEPREFIX` writes a bytecode file
  into the tree. Inside the starting files, that file fails `PAR-7`. Run the
  suite through a `just` recipe, which sets the variable.
- `uv` can serve a cached wheel at the same version. If a shipped file disagrees
  with the checkout, build the wheel again before reading the disagreement as a
  defect.
