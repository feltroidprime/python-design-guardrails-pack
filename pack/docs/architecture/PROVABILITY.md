# Provability

## A new capability

Do not write a product property before the product capability exists. When one
exists, add its catalog, its oracle, its production contract, its Hypothesis
evidence and its symbolic target as one coherent vertical change. The proof
guard then aggregates it with everything else the tree proves.

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
pack-owned, and a pack-owned catalog cannot name a target without writing the
package name. Mandatory proof coverage is therefore product behavior: a
capability declares its own laws in its own `proof.toml`, and a project with no
capability mandates nothing. ADR-0006 records the decision.

## Evidence sequence

1. Run `just prove` after you change a law or its evidence.
2. Run `just prove-one PROPERTY-ID` to narrow the loop to one changed law.
3. Run `just proof-report` to read the active property and evidence matrix.
4. Run `just prove-deep` only when a larger generated, stateful or symbolic
   search is worth its time.
5. Run `just check` before handoff and report its exact outcome. See
   `AGENTS.md` for what else a change requires.

## Independent oracles

An oracle takes explicit facts as parameters and returns a `bool`. It computes
that answer from the parameters alone, through a route independent of the
behavior it judges. It lives in the domain layer of the capability that owns
the decision. It must not read ambient state or perform I/O.

## Canaries and symbolic evidence

Every law has a plausible falsifying canary. The symbolic layer also runs
`pack/verification/harness/symbolic_canary.py`, whose deliberately false
`refutable_echo` postcondition must be refuted. A symbolic run is evidence
only when it reports at least one analysed target. Before you accept the run,
read the target count.
