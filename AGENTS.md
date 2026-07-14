# AGENTS.md — maintainer contract for the template pack

This file is normative for every coding agent and human working **on this
repository**. It governs the meta-repository only.

## What this repository is

This is a **meta-repository**. It does not ship an application; it generates
opinionated Python 3.14 repositories. The generated repositories are the
product.

- `copier.yml` defines the generation engine: typed and validated answers,
  strict Jinja rendering, the `template/` subdirectory, and artifact exclusions.
  `instantiate.py` is the stable adapter over pinned Copier and the module behind the
  installable `python-repo` console script (`python-repo init <name>
  [directory] [--package NAME] [--public] [--no-github] [--no-git]`); the
  root `pyproject.toml` exists solely to package that CLI plus `template/`
  for `uv tool install` (see `just install`). The `init` subcommand also
  runs `git init` + initial commit and `gh repo create --private … --push`;
  the legacy positional form stays purely local (no git, no gh, no network)
  because the pack's tests and `validate_pack.py` depend on that. Tests for
  the gh behavior must use a PATH-stubbed `gh`, never the real one.
- `template/` is the canonical source of every generated repository. Files and
  paths ending in `.jinja` are rendered by Copier; all others are copied verbatim.

## Two contracts, do not confuse them

- **This file** tells you how to maintain the pack.
- **`template/AGENTS.md` is downstream content, not your operating contract.**
  It is shipped to generated repositories and addresses agents working there.
  Edit it deliberately as product content; never follow its workflow here
  (there is no `uv run python scripts/quality_gate.py` at the root), and never
  let root-only tooling or wording leak into it.

The same applies to every file under `template/`: `template/justfile`,
`template/pyproject.toml.jinja`, and `template/scripts/` describe the downstream
repository, not this one.

## Sources of truth

| Concern | Source of truth |
|---|---|
| Everything a generated repository contains | `template/**` |
| Copier questions, rendering policy, and artifact exclusion | `copier.yml` |
| Stable generation and CLI behavior | `instantiate.py` |
| `python-repo` CLI packaging (console script, wheel contents) | `pyproject.toml` (root) |
| Downstream architecture policy | `template/architecture.toml.jinja` + `template/scripts/architecture_rules.py` |
| Downstream agent contract | `template/AGENTS.md` |
| Downstream quality gate | `template/scripts/quality_gate.py` (mirrored by `template/.github/workflows/quality.yml` and the pre-push hook) |
| Pack validation loop | `justfile` (root) + `scripts/validate_pack.py` + `tests/test_instantiate.py` |
| Curriculum-to-guardrail rationale | `DESIGN_MASTERY_MAPPING.md` |
| Last executed validation record | `VALIDATION.md` |

## Change protocol

1. **Fix the canonical source.** A defect observed in a generated repository is
   fixed under `template/` (or in `instantiate.py`), never by patching a
   generated copy. Generated copies are throwaway.
2. **Keep the Copier dependency explicit and pinned.** The generator deliberately
   depends on Copier: it replaces bespoke rendering with a maintained engine and
   records provenance for downstream updates. The root remains venv-less and
   lock-free; root generation entry points provision the exact pin with
   `uv run --no-project --with`.
3. **Never weaken a downstream guardrail silently.** Loosening any ceiling,
   lint rule, type setting, coverage floor, or architecture rule in
   `template/` requires an explicit rationale in the change description and an
   update to `DESIGN_MASTERY_MAPPING.md` when the mapping changes.
4. **Keep version pins coherent.** The pinned toolchain appears in several
   places that must move together: `template/pyproject.toml.jinja` (dev group and
   `tool.uv.required-version`), `template/.pre-commit-config.yaml` (hook
   revisions), and `template/.github/workflows/quality.yml` (uv version).
   Two diagram-toolchain pins join this rule: the grimp pin appears in
   `template/pyproject.toml.jinja` (dev group) **and** the root `justfile`
   (`--with grimp==…` for the diagram-sync tests) — move both together. The
   LikeC4 CLI version is pinned in exactly one place, `[tool.likec4]` in
   `template/pyproject.toml.jinja`; never introduce a second copy. The Copier
   pin appears in the root `pyproject.toml`, both generating recipes in the root
   `justfile`, the benchmark bootstrap in `benchmarks/run.py`, and
   `_min_copier_version` in `copier.yml`; move all together. The root project
   version is the wheel fallback for Copier's `_commit`, so release wheels must
   use the corresponding template tag version.
5. **No local artifacts in `template/`.** Runtime caches (`.ruff_cache`,
   `__pycache__`, `.pytest_cache`, …) must never exist there; the authoritative
   pattern list is `_exclude` in `copier.yml`. Note that
   `template/.gitignore` hides such artifacts from `git status`, so a clean
   status does **not** prove a clean template — `just validate` checks the
   filesystem directly.
6. **Jinja rendering.** Any template file whose content needs rendering must end
   in `.jinja`; templated path components use Jinja directly. Strict undefined
   makes unknown variables fail generation, and validation rejects stray Jinja
   syntax or `.jinja` suffixes in generated output. Keep files containing other
   template syntax, such as GitHub Actions `${{ }}`, verbatim unless they also
   need Copier rendering.
7. **Throwaway repositories stay out of the tree.** Generate validation or
   experiment repositories only in temporary directories (the validation
   script already does this), never inside this working tree.

## Validation requirements

The canonical command is:

```bash
just validate
```

It runs the generator unit tests, then instantiates a fresh repository in a
temporary directory, verifies template cleanliness and complete Jinja
rendering, resolves the pinned dependencies, runs the generated repository's
own quality gate, and cleans up.

Required before claiming completion:

- change to `instantiate.py` or anything under `template/` → `just validate`;
- change to root tests/validation scripts → `just validate`;
- docs-only change at the root → no run required, but commands quoted in docs
  must match the justfile and scripts.

`just test` alone (generator tests, no downstream install) is a fast inner
loop, not a completion criterion for template changes.

Prerequisites: `python3` (3.14), `uv`, `just`, `bun`, and network access for
the first dependency resolution (including the first `bunx` download of the
pinned LikeC4 CLI, exercised by the downstream gate's `diagram views` check).
`uv run --no-project --with` supplies Copier, pytest, and grimp; the root
`pyproject.toml` is packaging-only (Copier is its sole runtime dependency; it
has no dev tooling) and the
root intentionally has no virtualenv or lock file, so IDE warnings about
unresolved `pytest`/`validate_pack`/`grimp` imports are expected. If you
change what a wheel must ship (new top-level template asset, renamed
generator), update the hatchling include/force-include sections in the root
`pyproject.toml` in the same change.

## Documentation synchronization

When behavior changes, update the documents that state it, in the same change:

- root `README.md`: maintainer commands and the instantiation walkthrough;
- `template/README.md.jinja` and `template/AGENTS.md`: downstream commands, only if
  downstream behavior changed;
- `DESIGN_MASTERY_MAPPING.md`: when a guardrail is added, removed, or
  materially changed;
- `VALIDATION.md`: replace the record when you re-run full validation after a
  material change; date it and state the environment honestly.

## Completion reporting

A completion report must state:

- files changed and why;
- tests added or updated;
- exact commands executed and their actual results;
- whether `just validate` was run and its outcome;
- remaining risks or portability caveats.

Never claim a validation you did not execute. If the gate fails, report the
failure verbatim rather than narrowing the claim.
