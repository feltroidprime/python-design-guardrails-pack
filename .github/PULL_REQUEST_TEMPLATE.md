## Intent

What user/domain behavior changes?

## Design

- Owning layer:
- Existing abstraction extended:
- New pattern or dependency introduced: no / ADR-XXXX
- Dependency direction changed: no / explain

## Property delta

- Added/changed property IDs:
- Exact scope of each changed property:
- Minimal counterexample for each changed property:
- External assumptions that remain outside the pure proof boundary:
- `proof/policy.toml` or an ownership-zone catalog changed: yes / no — why

## Tests and evidence

- [ ] The oracle is primitive-fact based, effect-free, and independent from the behavior it judges
- [ ] `icontract` pre/postcondition or invariant calls the declared oracle
- [ ] One canonical Hypothesis proof invokes the exact declared target and oracle
- [ ] One falsifying canary exists for every changed property
- [ ] Stateful behavior uses one literal local `RuleBasedStateMachine`; only reachable rules/helpers carry evidence
- [ ] Every contracted public function or method is a CrossHair target
- [ ] Regression/example tests cover the concrete bug or user path
- [ ] Port contract tests cover adapter changes
- [ ] CLI catalog changes have independent input/query/retry/safety/outcome process cases
- [ ] `just prove-one PROPERTY-ID` (or `just prove`) and `just check` pass

## Change amplification

Which modules and callers had to change? Is that spread expected or evidence of a missing/incorrect boundary?

## Migration / rollback

Required for behavior changes with persistent data, external integrations, concurrency, or staged rollout.
