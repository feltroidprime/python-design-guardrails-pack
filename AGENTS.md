# AGENTS.md — maintainer contract for the template pack

This file is normative for every coding agent and human working **on this
repository**. It governs the meta-repository only.

## What this repository is

This is a **meta-repository**. It does not ship an application; it generates
opinionated Python 3.14 repositories. The generated repositories are the
product.

- `instantiate.py` is the generator. It copies `template/` into a target
  directory, renames `src/__PACKAGE__`, and replaces the placeholder tokens
  `__PROJECT_NAME__` and `__PACKAGE__`.
- `template/` is the canonical source of every generated repository, verbatim
  except for placeholder substitution.

## Two contracts, do not confuse them

- **This file** tells you how to maintain the pack.
- **`template/AGENTS.md` is downstream content, not your operating contract.**
  It is shipped to generated repositories and addresses agents working there.
  Edit it deliberately as product content; never follow its workflow here
  (there is no `uv run python scripts/quality_gate.py` at the root), and never
  let root-only tooling or wording leak into it.

The same applies to every file under `template/`: `template/justfile`,
`template/pyproject.toml`, and `template/scripts/` describe the downstream
repository, not this one.

## Sources of truth

| Concern | Source of truth |
|---|---|
| Everything a generated repository contains | `template/**` |
| Generation logic, name validation, placeholder tokens, artifact exclusion | `instantiate.py` |
| Downstream architecture policy | `template/architecture.toml` + `template/scripts/architecture_rules.py` |
| Downstream agent contract | `template/AGENTS.md` |
| Downstream quality gate | `template/scripts/quality_gate.py` (mirrored by `template/.github/workflows/quality.yml` and the pre-push hook) |
| Pack validation loop | `justfile` (root) + `scripts/validate_pack.py` + `tests/test_instantiate.py` |
| Curriculum-to-guardrail rationale | `DESIGN_MASTERY_MAPPING.md` |
| Last executed validation record | `VALIDATION.md` |

## Change protocol

1. **Fix the canonical source.** A defect observed in a generated repository is
   fixed under `template/` (or in `instantiate.py`), never by patching a
   generated copy. Generated copies are throwaway.
2. **Keep `instantiate.py` standard-library-only.** No third-party imports, no
   downloads. It must run with a bare `python3`.
3. **Never weaken a downstream guardrail silently.** Loosening any ceiling,
   lint rule, type setting, coverage floor, or architecture rule in
   `template/` requires an explicit rationale in the change description and an
   update to `DESIGN_MASTERY_MAPPING.md` when the mapping changes.
4. **Keep version pins coherent.** The pinned toolchain appears in several
   places that must move together: `template/pyproject.toml` (dev group and
   `tool.uv.required-version`), `template/.pre-commit-config.yaml` (hook
   revisions), and `template/.github/workflows/quality.yml` (uv version).
5. **No local artifacts in `template/`.** Runtime caches (`.ruff_cache`,
   `__pycache__`, `.pytest_cache`, …) must never exist there; the authoritative
   pattern list is `IGNORED_ARTIFACT_PATTERNS` in `instantiate.py`. Note that
   `template/.gitignore` hides such artifacts from `git status`, so a clean
   status does **not** prove a clean template — `just validate` checks the
   filesystem directly.
6. **Placeholders.** If you introduce a new placeholder token in `template/`,
   add it to `PLACEHOLDER_TOKENS` in `instantiate.py` in the same change;
   the placeholder scan in validation fails otherwise.
7. **Throwaway repositories stay out of the tree.** Generate validation or
   experiment repositories only in temporary directories (the validation
   script already does this), never inside this working tree.

## Validation requirements

The canonical command is:

```bash
just validate
```

It runs the generator unit tests, then instantiates a fresh repository in a
temporary directory, verifies template cleanliness and full placeholder
replacement, resolves the pinned dependencies, runs the generated repository's
own quality gate, and cleans up.

Required before claiming completion:

- change to `instantiate.py` or anything under `template/` → `just validate`;
- change to root tests/validation scripts → `just validate`;
- docs-only change at the root → no run required, but commands quoted in docs
  must match the justfile and scripts.

`just test` alone (generator tests, no downstream install) is a fast inner
loop, not a completion criterion for template changes.

Prerequisites: `python3` (3.14), `uv`, `just`, and network access for the
first dependency resolution. `uv run --with pytest` supplies pytest; the root
intentionally has no `pyproject.toml` and no virtualenv, so IDE warnings about
unresolved `pytest`/`validate_pack` imports in `tests/` are expected.

## Documentation synchronization

When behavior changes, update the documents that state it, in the same change:

- root `README.md`: maintainer commands and the instantiation walkthrough;
- `template/README.md` and `template/AGENTS.md`: downstream commands, only if
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
