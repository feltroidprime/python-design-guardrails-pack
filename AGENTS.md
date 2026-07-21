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
  for `uv tool install` (see `just install`). The `init` subcommand also runs
  `git init`, `just bootstrap` (dependency sync, prek hook installation, and
  the generated quality gate), the initial commit, and
  `gh repo create --private … --push`, in that order;
  the legacy positional form stays purely local (no git, no gh, no network)
  because the pack's tests and `validate_pack.py` depend on that. Tests for
  the gh behavior must use a PATH-stubbed `gh`, never the real one.
- `template/` is the canonical source of every generated repository. Files and
  paths ending in `.jinja` are rendered by Copier; all others are copied verbatim.

## Two contracts, do not confuse them

- **This file** tells you how to maintain the pack.
- **The conditional `AGENTS.md` template under `template/` is downstream content,
  not your operating contract.**
  It is shipped to generated repositories and addresses agents working there.
  Edit it deliberately as product content; never follow its workflow here
  (there is no `uv run python scripts/quality_gate.py` at the root), and never
  let root-only tooling or wording leak into it.

The same applies to every file under `template/`: `template/justfile.jinja`,
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
| Downstream agent contract | `template/{% if agents_contract != 'none' %}AGENTS.md{% endif %}.jinja` |
| Downstream quality gate | `template/scripts/quality_gate.py.jinja` (mirrored by `template/.github/workflows/quality.yml.jinja` and the pre-push hook) |
| Optional derived-diagram feature | the `likec4` question in `copier.yml`, `--likec4` in `instantiate.py`, and every `likec4` Jinja branch under `template/` |
| Pack validation loop | `justfile` (root) + `scripts/validate_pack.py` + `tests/test_instantiate.py` |
| Design-to-guardrail rationale | `DESIGN_GUARDRAILS.md` |
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
   update to `DESIGN_GUARDRAILS.md` when the mapping changes.
4. **Keep version pins coherent.** Several pins deliberately exist in more
   than one place (Copier, uv, the prek floor, grimp, pytest-xdist, the
   private session-profiler commit, the single-source LikeC4 CLI version).
   `tests/test_pin_coherence.py` discovers every occurrence by scanning the
   tracked tree and fails `just test` when any copy disagrees, so there is no
   location list to memorize: move a pin, then update the copies the test
   reports until it passes, and register any new multi-location pin in that
   test in the same change. Two release-time couplings remain judgment calls:
   the root project version is the wheel fallback for Copier's `_commit`, so
   release wheels must use the corresponding template tag version, and the
   session-profiler commit stays out of the generated dependency groups and
   lockfile so baseline bootstrap and CI remain credential-free.
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
own quality gate, and cleans up. It instantiates the **default** answers, so
the LikeC4 assets are absent from that run; `just validate likec4` performs the
same loop against the opt-in configuration, including the gate's `diagram sync`
and `diagram views` checks.

Required before claiming completion:

- change to `instantiate.py` or anything under `template/` → `just validate`;
- change to root tests/validation scripts → `just validate`;
- change to any `likec4`-conditional branch, the sync script, or the LikeC4
  assets → `just validate likec4` as well, since the default run never
  instantiates that configuration;
- docs-only change at the root → no run required, but commands quoted in docs
  must match the justfile and scripts.

`just test` alone (generator tests, no downstream install) is a fast inner
loop, not a completion criterion for template changes.

Prerequisites: `python3` (3.14), `uv`, `just`, and network access for the first
dependency resolution. `just validate likec4` additionally requires `bun`: it
generates the opt-in LikeC4 configuration, whose gate downloads the pinned
LikeC4 CLI through `bunx` for its `diagram views` check.
`uv run --no-project --with` supplies Copier, pytest, pytest-xdist, and grimp;
the root `pyproject.toml` is packaging-only (Copier is its sole runtime
dependency; it has no dev tooling) and the
root intentionally has no virtualenv or lock file, so IDE warnings about
unresolved `pytest`/`validate_pack`/`grimp` imports are expected. If you
change what a wheel must ship (new top-level template asset, renamed
generator), update the hatchling include/force-include sections in the root
`pyproject.toml` in the same change.

## Documentation synchronization

When behavior changes, update the documents that state it, in the same change:

- root `README.md`: maintainer commands and the instantiation walkthrough;
- `template/README.md.jinja` and the conditional `AGENTS.md` template: downstream commands, only if
  downstream behavior changed;
- `DESIGN_GUARDRAILS.md`: when a guardrail is added, removed, or
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

## Agent skills

### Issue tracker

Specs and tickets live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the five standard triage labels, including
`ready-for-agent`. See `docs/agents/triage-labels.md`.

### Domain docs

The repository uses a single-context domain documentation layout. See
`docs/agents/domain.md`.

<!-- vendored-docs:begin -->
## Vendored documentation

Before writing code against these libraries, read the page named below instead of recalling the
API from memory. These trees are pinned and read-only; `vendor-docs check` fails on local edits.

| Read | When | Pin |
|---|---|---|
| `docs/vendored/arize_phoenix/phoenix/` | before choosing Phoenix capabilities for an AI application | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/get-started/` | before adding Phoenix to an application | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/tracing/` | before instrumenting application tracing or annotating spans | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/evaluation/` | before implementing Phoenix evaluators or server-side evaluations | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/datasets-and-experiments/` | before creating Phoenix datasets or experiment workflows | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/prompt-engineering/` | before storing, versioning, or testing prompts with Phoenix | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/integrations/` | before wiring Phoenix to a provider, framework, language, or coding agent | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/` | before choosing a local, notebook, container, or cloud Phoenix environment | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/self-hosting/` | before deploying or upgrading a self-hosted Phoenix instance | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/` | before hardening a Phoenix tracing pipeline or server for production | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/settings/` | before configuring Phoenix authentication, access control, providers, secrets, or sandboxes | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/cookbook/` | before adapting an end-to-end Phoenix workflow pattern | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/use-cases/` | before evaluating a RAG application with Phoenix | arize-phoenix-v18.0.0 |
| `docs/vendored/arize_phoenix/phoenix/resources/frequently-asked-questions/` | before troubleshooting Phoenix setup or behavior | arize-phoenix-v18.0.0 |
<!-- vendored-docs:end -->
