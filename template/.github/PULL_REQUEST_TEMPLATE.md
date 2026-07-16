## Intent

What user/domain behavior changes?

## Design

- Owning layer:
- Existing abstraction extended:
- New pattern or dependency introduced: no / ADR-XXXX
- Dependency direction changed: no / explain

## Invariants and failure modes

What invalid states, retries, cancellation, cleanup, or external failures were considered?

## Tests and evidence

- [ ] Regression/example tests
- [ ] Property tests where invariants have a broad input space
- [ ] Port contract tests for adapter changes
- [ ] `just check` passes

## Change amplification

Which modules and callers had to change? Is that spread expected or evidence of a missing/incorrect boundary?

## Migration / rollback

Required for behavior changes with persistent data, external integrations, concurrency, or staged rollout.
