# One-source packaging — prototype findings

PROTOTYPE — throwaway. Answers [#80](https://github.com/feltroidprime/python-design-guardrails-pack/issues/80).

## Question

Can one valid root `pyproject.toml` and one real project tree support Root Pack
development, distribution of the external CLI, closed identity projection, and
creation of a valid Terminal Project, without a second pyproject, a Jinja source
tree, or a hidden template copy?

## Answer

Yes, with the `uv_build` backend and a build-time `git archive` blob.

## How it was measured

`proto_pack.py` materializes a scratch Root Pack (19 files: `pyproject.toml`,
`justfile`, `AGENTS.md`, `README.md`, `CHANGELOG.md`, `scripts/`, `tests/`, and
`src/guardrails_pack/` holding a `cli`, a `widget` capability, and a `bootstrap`
capability with `initial/` and the projection code). It then runs, for each
packaging variant:

1. `uv sync`, `uv run pytest`, `uv run pyrepo` — Root Pack development;
2. `uv build --wheel`, `uv venv`, `uv pip install <wheel>` — external CLI;
3. `pyrepo init my-product`, run from the installed console script only;
4. `uv sync`, `uv run pytest`, `uv run my-product`, `uv build --wheel` inside the
   Terminal Project, plus a scan for surviving pack tokens and a scan of the
   wheel it produces.

Nothing is mocked. Every row below is a real command result.

## Results

| Measure | hatchling `force-include` | uv_build + staged directory | uv_build + `git archive` blob |
|---|---|---|---|
| Pack-only lines in `pyproject.toml` | 8 | 0 | 0 |
| Terminal `pyproject.toml` clean | no | yes | yes |
| Terminal `.venv` clean | no | yes | yes |
| Terminal wheel clean | no — 12 of 21 entries | yes | yes |
| Root gate polluted by the artifact | n/a | yes, doubles every finding | no, 0 added |
| Artifact under `src/` | none | 19-file directory | 1 file |
| Shipped tree equals | an 8-entry manifest | the working tree | the last commit |

Common to all three variants, and all passing: Root Pack development, wheel
build, wheel install, projection from the installed CLI, no surviving bootstrap
capability, no pack-token leak, and a Terminal Project that syncs, tests, runs
its own console script, and builds.

## Why hatchling loses

`force-include` is a table inside the file being projected, so the identity swap
rewrites it instead of removing it:

```toml
# Root Pack
"src" = "guardrails_pack/_pack_tree/src"
# every Terminal Project, after projection
"src" = "my_product/_pack_tree/src"
```

The stanza cannot erase itself. Measured consequence: the Terminal Project's own
wheel carries 12 entries of duplicated source, and its `.venv` carries the copy
too. It also needs an explicit manifest of top-level entries, which drifts
silently when a new root file is added.

## Why the blob beats the staged directory

`uv_build` includes whatever sits under the module root, so the pyproject needs
no packaging table at all — inclusion is by presence, not by declaration. The
staged-directory form pays for that with lint pollution: with one injected error
in `widget/api.py`, Ruff reported 4 findings instead of 2, half of them inside
`src/guardrails_pack/_pack_tree/`. The single-file form reported 2.

`git archive HEAD` also fixes what the shipped tree *is*: exactly the committed
tree, never untracked junk and never a dirty working tree.

## The shape this settles

```toml
[build-system]
requires = ["uv_build==0.12.0"]
build-backend = "uv_build"

[project]
name = "pyrepo"
...

[project.scripts]
pyrepo = "guardrails_pack.cli:main"

[tool.uv.build-backend]
module-name = "guardrails_pack"
```

`just build` becomes: `git archive HEAD -o src/guardrails_pack/_pack.tar`, then
`uv build --wheel`, then delete the blob.

`module-name` is needed only because the pack's distribution name (`pyrepo`) and
its import name (`guardrails_pack`) differ. After projection the two agree
(`my-product` / `my_product`), so the line is correct and inert downstream.

## Two facts the specification must carry

1. **The projection source has two locations.** Installed, it is
   `<package>/_pack.tar`. In the Root Pack's own checkout the blob is absent, so
   the code falls back to the repository root. Both paths are exercised by the
   prototype.
2. **`git archive HEAD` ships the commit, not the working tree.** A release must
   therefore commit first. An interrupted build can leave the blob behind, so the
   quality gate must ignore `src/*/_pack.tar`.

## Also demonstrated

The command line discovers `init` by scanning `capabilities/`; deleting the
bootstrap directory deletes the subcommand, with no registry and no generated
index. This is context for
[#89](https://github.com/feltroidprime/python-design-guardrails-pack/issues/89),
not a resolution of it.

## Run it

```bash
python3 prototype/one-source-packaging/proto_pack.py both
```
