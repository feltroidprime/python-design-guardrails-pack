# Python Design Guardrails Pack

The Root Pack. It is one real Python 3.14 project, and it starts one more like
itself. A new project receives the architecture policy, the tool policy, the
proof system and the twelve-hook gate, and it chooses its own product model.

There is one tree. The pack is the product, so a defect is fixed exactly once,
and every tool checks the shipped files in place.

## Start a project

You need Python 3.14, [uv](https://docs.astral.sh/uv/) and
[just](https://github.com/casey/just). Install
[gh](https://cli.github.com/) as well when you want the pack to create the
GitHub repository.

```bash
uv tool install pyrepo
pyrepo bootstrap init my-product ./my-product
cd my-product
just check
```

`init` refuses a bad name before it writes anything. It then builds the whole
project in a temporary directory, checks the result, and moves it into place as
one operation. After that it runs `git init`, `just setup`, and the first
commit. A failure at any stage leaves your disk untouched.

`init` never reaches the network. Add `--github` to create and push the
repository, and `--public` to select its visibility. Add `--package NAME` to
choose an import name other than the derived one.

## Update a project

```bash
pyrepo bootstrap update ./my-product
```

The update replaces whole pack-owned files and writes no user-owned file, so
current tool policy reaches a project that already exists. It refuses a dirty
worktree, a newer project version, and any local change to a pack-owned file.
`--force` overwrites and saves the replaced bytes under a backup directory
inside `pack/`. An update never runs the gate: a red gate on your own code
afterwards is the intended signal.

## What a new project owns

```
pack/                    pack-owned: configs, guards, proof policy, the gate
src/<package>/
  _foundation/           pack-owned: the router, the envelopes, the outcomes
  cli.py                 yours: a two-line entry point
  composition.py         yours: CAPABILITIES = ()
justfile                 yours: one import of pack/justfile
pyproject.toml           yours: identity, dependencies, packaging
```

A Product Capability is one directory directly under the package, plus one
import line in `composition.py`. Nothing else records it. The router then
derives the command line from the public functions of its `api.py`.

## Work on the pack

```bash
just setup
just check
just prove
```

`just check` is the one gate, and CI runs the same command. The gate is
identical in this repository and in every project the pack starts, and it has
no branch that depends on which one it runs in.

The acceptance suite carries the 53 assertions of the refactor. It is capability
code, it is marked `acceptance`, and it runs from an installed console script
rather than from this checkout, because a source checkout hides a packaging
defect. The `tests` hook of the gate excludes the marker, and a separate CI job
runs it.

```bash
uv run pytest -c pack/configs/pytest.ini --rootdir=. -m acceptance
```

Read `AGENTS.md` for the contract this repository holds you to,
`DESIGN_GUARDRAILS.md` for the design-to-guardrail map, `CONTEXT.md` for the
vocabulary, and `docs/README.md` for the documentation map.
