# Python Design Guardrails Pack

Generate a Python 3.14 repository that begins at **N0**: a valid repository
with architecture, ownership, documentation, proof, and quality controls, but
no shipped product capability. It supplies `repoctl` to inspect and evolve the
repository; the product model remains the repository owner's decision.

## Start a repository

Requires Python 3.14, [uv](https://docs.astral.sh/uv/), and
[just](https://github.com/casey/just). Install
[gh](https://cli.github.com/) when the initializer should create the GitHub
repository too.

```bash
just install
python-repo init my-product .
cd my-product
```

The normal initializer creates the project, initializes Git, runs
`just bootstrap`, creates the initial commit, then creates and pushes a private
GitHub repository. Use `--public`, `--no-github`, `--no-git`, or
`--package NAME` when appropriate. The legacy positional form is local only;
it does not initialize Git or contact GitHub.

The generated repository starts with these useful commands:

```bash
just check
uv run python -m repoctl status
just prove
```

`repoctl` is the repository-control command surface. It can inspect repository
state and manage future capabilities without choosing a product model for the
owner.

## What N0 owns

N0 deliberately ships only shared structure:

- `repoctl/` contains repository-control behavior.
- `src/<package>/_foundation/` holds shared product-package protocol support.
- `src/<package>/_generated/` holds replaceable generated indexes.
- `architecture.toml`, `proof/`, `scripts/`, and the quality gate enforce
  ownership, dependency, evidence, and documentation rules.

Product capabilities belong under the product ownership roots declared in
`architecture.toml`; none is preselected by the template.

## Workspace members

Set `workspace_member: true` for a uv workspace member. The workspace root then
owns the lockfile, environment, development dependencies, and shared tool
configuration. The generated member keeps its package metadata, ownership
rules, and repository-control surface.

## Maintaining this pack

This is a meta-repository: `template/` is the generated product,
`copier.yml` owns rendering, `instantiate.py` owns the CLI, and root
`AGENTS.md` is the maintainer contract.

```bash
just check
just test
just validate
```

Run `just validate` for changes to the template, generator, root tests, or
validation scripts. It generates a throwaway N0 repository and runs its full
quality gate. `just test` includes the real N0 → N1 → N2 acceptance walk and
has a seven-minute warm-cache budget; use `just test-fast` for sub-minute
feedback. See `DESIGN_GUARDRAILS.md` for the enforcement map and `VALIDATION.md`
for the latest full-validation record.
