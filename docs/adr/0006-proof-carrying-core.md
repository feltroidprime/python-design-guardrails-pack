# ADR-0006: Critical decisions carry executable evidence

- Status: accepted
- Date: 2026-08-05
- Owners: repository maintainers
- Revisit trigger: the proof system cannot express a law, or a capability needs
  an evidence form that the system does not have

## Context and forces

A project starts with no product behavior to prove, and it must still prove the
rules that protect its future capabilities. An empty discovery must never make
the proof hook look green by accident.

## Decision

`pack/proof/policy.toml` holds the shared discovery configuration, and each
catalog beside it declares one set of laws. The proof guard connects every law
to a pure oracle, an `icontract` target, Hypothesis evidence, and a bounded
CrossHair target. `pack/verification/harness/symbolic_canary.py` stays a
deliberately false contract that CrossHair must refute, so an empty symbolic
search cannot pass as a successful one.

Discovery is structural. The guard reads every `*.toml` below `pack/proof/` and
the `proof.toml` of each capability directory. No file lists a catalog root, so
no list can disagree with the tree.

`_foundation/` is pack-owned and holds no product law. A pack-owned catalog
would have to write the package name to name a target, and invariant O1 of #85
forbids project identity inside a pack-owned file. Mandatory proof coverage is
therefore product behavior: each capability declares its own laws in its own
`proof.toml`, and a project with no capability mandates nothing.

## Alternatives considered

- **A made-up product law.** Rejected: invented semantics are not evidence.
- **No canary for an empty behavior root.** Rejected: an empty symbolic search
  would look the same as a successful one.

## Consequences

### Positive

- The decisions that protect the tree are checked, not asserted in prose.
- A new capability enters the same proof system through its own catalog.

### Negative / cost accepted

- A new project reports no product property until it has a capability.

### Risks and mitigations

- *A catalog loses contact with the code:* the proof guard resolves every
  target, oracle and evidence link before any test runs.

## Validation

`just prove` runs proof closure, the evidence suite and the bounded symbolic
gate. `just proof-report` prints the active property and evidence matrix. The
`proof` and `symbolic` hooks of the gate run the same checks.

## Migration and rollback

Add a product law only when a capability exists. Keep the canary whenever the
proof surface changes, so symbolic execution cannot disappear in silence.

## Removal / supersession criteria

Supersede this ADR only with an evidence system that keeps independent oracles,
executable counterexamples and explicit symbolic targets.
