# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.12.0, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

The pack now uses the current uv 0.12.0 release consistently.

- The root and generated-repository GitHub workflows use the latest published
  `astral-sh/setup-uv@v9.0.0` action and install uv 0.12.0 explicitly.
- Generated repositories use `uv_build==0.12.0`, require uv `>=0.12.0,<0.13`,
  and use the matching 0.12.0 `uv-pre-commit` hook.
- The pin-coherence test now covers the generated build backend and the root
  workflow too, preventing a future partial uv upgrade.

## Commands and actual results

```bash
uv --version
just validate
```

`uv --version` reported **0.12.0**. The previously failing generated
vertical-slice, tracked-syntax, and update-preservation cases passed together
under uv 0.12.0 (**3 passed** in 10.12s); the exact offline update-roundtrip
case then passed in 61.27s after the policy commit was visible to its cloned
template source.

The final canonical `just validate` passed end to end (directly observed exit
code 0):

- root Ruff repair/check was stable across 139 files; root tests: **215
  passed** in 27.69s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- each generated full quality run reported **252 passed, 8 skipped, 3
  deselected** with **93.94%** coverage;
- the committed Copier update round trip and offline downstream gate completed
  **2 passed in 65.74s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess environment and filesystem behavior can differ.
- uv is deliberately pinned at 0.12.0 across the generated build/tooling
  surface. A later uv release requires an explicit coherent-pin update and
  another full validation run.
