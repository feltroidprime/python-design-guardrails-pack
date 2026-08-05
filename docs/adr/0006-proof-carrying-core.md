# ADR-0006: Repository-control decisions carry executable evidence

- Status: accepted
- Date: 2026-07-30
- Owners: repository maintainers
- Revisit trigger: the proof system cannot express a repository-control law or
  a declared capability needs an additional evidence form

## Context and forces

N0 has no product behavior to prove, but it must prove the control plane that
creates and protects future product capabilities. Empty discovery must not make
the proof gate look green by accident.

## Decision

`proof/policy.toml` defines shared discovery while `proof/repoctl/` declares
repository-control laws. The proof guard connects each law to a pure oracle,
an `icontract` target, Hypothesis evidence, and bounded CrossHair analysis.
`verification/harness/symbolic_canary.py` remains a deliberately false contract
that CrossHair must refute.

N0's package `_foundation` is an empty behavior boundary. It contributes no
placeholder law; repository-control properties remain the executable proof
exemplar.

## Alternatives considered

- **A fabricated product law.** Rejected: invented semantics are not evidence.
- **No canary for empty behavior roots.** Rejected: an empty symbolic search
  would be indistinguishable from a successful one.

## Consequences

### Positive

- The generator's critical decisions remain independently checked in N0.
- Future capabilities enter the same proof system through their declaration.

### Negative / cost accepted

- The baseline proof report is intentionally about repository control only.

### Risks and mitigations

- *A catalog becomes detached from code:* the proof guard resolves exact
  targets, evidence, and oracles before tests run.

## Validation

`just prove` runs proof closure, repository-control evidence, and the bounded
symbolic gate. `just proof-report` prints the active property/evidence matrix.

## Migration and rollback

Add product laws only when a product capability exists. Keep the canary when
the proof surface changes so symbolic execution cannot silently disappear.

## Removal / supersession criteria

Supersede this ADR only with an evidence system that preserves independent
oracles, executable counterexamples, and explicit symbolic targets.
