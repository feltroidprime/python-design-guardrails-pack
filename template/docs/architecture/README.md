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

## Architecture profile

This template uses the `system` profile. Tiny scripts may collapse layers only through an ADR explaining why the reduced structure remains legible. Do not retain empty ceremonial layers; either use the boundary or remove it deliberately.

## Fitness functions

- Import Linter checks dependency direction and adapter independence.
- `scripts/architecture_guard.py` checks domain purity, immutability conventions, suppressions, names, and size ceilings.
- BasedPyright checks contracts and exhaustive variants.
- Ruff checks complexity, error handling, security, performance, and style.
- pytest contract tests verify adapter substitutability.
