# Architecture

## Dependency direction

```text
bootstrap
   ↓
adapters
   ↓
application
   ↓
domain
```

A higher layer may depend on a lower layer. A lower layer never depends on a higher layer. Inbound and outbound adapters are independent siblings.

## Stable seams

- Domain objects protect invariants.
- Application use cases own workflow decisions.
- Application ports name capabilities required from the outside world.
- Adapters translate concrete technologies into those capabilities.
- Bootstrap owns object construction and production configuration.
- The CLI catalog is the sole command-registration seam; argparse translates
  immediately into typed inbound requests.

## Architecture profile

This template uses the `system` profile. Tiny scripts may collapse layers only through an ADR explaining why the reduced structure remains legible. Do not retain empty ceremonial layers; either use the boundary or remove it deliberately.

## Fitness functions

- Import Linter checks dependency direction and adapter independence.
- `scripts/architecture_guard.py` checks domain purity, immutability conventions, None discipline (ARCH016–ARCH018), Path discipline (ARCH019–ARCH020), and CLI discipline (ARCH021–ARCH024: no inbound prompt drift, uncontrolled exits, framework leakage, or uncataloged command names/aliases), plus suppressions, names, and size ceilings.
- BasedPyright checks contracts and exhaustive variants.
- Ruff checks complexity, error handling, security, performance, and style.
- pytest contract tests verify adapter substitutability.
- pytest's CLI contract compares the catalog with an independent closed case
  set, then exercises every command at the detached process seam.
- `scripts/sync_architecture_diagrams.py` derives the LikeC4 model under `likec4/generated/` from the same import graph Import Linter enforces; the gate fails when the committed model lags the code or a hand-written view references a missing element.

## Diagrams

- `likec4/generated/` — derived model and baseline views. Never hand-edited; regenerate with `just fix`.
- `likec4/views.c4` — team-owned free-form views.
- `just diagrams` serves the live viewer.
