# Provability

## The proof surface

`pack/proof/policy.toml` holds the shared discovery configuration, and each
catalog beside it declares one set of laws. Discovery is structural: the guard
reads every `*.toml` below `pack/proof/`, and the `proof.toml` of each
capability directory. No file lists a catalog root, so no list can disagree
with the tree.

Each declared law names its production target, its scope, its assumptions, an
independent oracle, an `icontract` condition, Hypothesis evidence, and a
CrossHair target. The proof guard rejects a missing link before the evidence
suite runs.

The `_foundation` boundary of the package holds no product law. It is
pack-owned, and a pack-owned catalog would have to write the package name to
name a target. Mandatory proof coverage is therefore product behavior: a
capability declares its own laws in its own `proof.toml`, and a project with no
capability mandates nothing. ADR-0006 records the decision.

## Evidence sequence

1. Run `just prove` after you change a law or its evidence.
2. Run `just proof-report` to read the active property and evidence matrix.
3. Run `just prove-deep` only when a larger generated, stateful or symbolic
   search is worth its time.
4. Run `just check` before handoff. It is the same twelve hooks that CI runs.

## Independent oracles

An oracle accepts explicit facts and returns `bool`. It must not import or call
the behavior it judges, read ambient state, perform I/O, or recover a result by
running production code again. Keep the oracle beside the decision it
describes, in the domain layer of the capability that owns that decision.

## Canaries and symbolic evidence

Every law has a plausible falsifying canary. The symbolic layer also runs
`pack/verification/harness/symbolic_canary.py`, whose deliberately false
`refutable_echo` postcondition must be refuted. A symbolic run that finds no
target is not accepted as evidence.

## A new capability

Do not write a product property before the product capability exists. When one
exists, add its catalog, its oracle, its production contract, its Hypothesis
evidence and its symbolic target as one coherent vertical change. The proof
guard then aggregates it with everything else the tree proves.
