# ADR-0006: Critical code carries an executable property contract

- Status: accepted
- Date: 2026-07-27
- Owners: repository maintainers
- Revisit trigger: a defect crosses the declared proof surface undetected, or
  `just prove` exceeds ten seconds on the reference project

## Context and forces

Example tests and line coverage show that code ran; they do not show that the
important law was stated. This matters more with coding agents: an agent can
quickly add a branch, mirror the examples it sees, reach the coverage floor,
and still omit replay safety, identity preservation, canonicalization, or a
legal-transition rule.

Proving arbitrary Python that performs GitHub, CLI, MCP, filesystem, process,
clock, and network effects is neither realistic nor useful in the daily loop.
The repository needs a deliberately small core whose behavior is easy to
specify, generate, and search symbolically, plus a mechanical rule preventing
critical behavior from silently escaping that core.

## Decision

The generated repository uses a closed proof chain built from `proof.toml`,
`icontract`, Hypothesis, and CrossHair.

1. `proof.toml` is the semantic index. Every property has a stable ID, a
   normative statement, exact scope, explicit external assumptions, failure
   modes, a concrete counterexample, production targets, pure oracle functions,
   and required evidence.
2. The public surface under the configured domain roots is closed.
   `scripts/proof_guard.py` rejects a new public class, function, or method
   unless a property owns it or a dated exemption names it.
3. Pure predicates in configured `specifications.py` modules are the executable
   specification. Production contracts and tests call those predicates instead
   of copying the same condition into several places. The guard rejects oracles
   that are non-boolean, effect-shaped, stored elsewhere, or coupled back to the
   behavior they judge, including known filesystem, process, network, clock, and
   randomness access.
4. `icontract` attaches preconditions, postconditions, and class invariants to
   production symbols. Every core contract has a literal
   `description="PROPERTY[ID]: ..."`; the guard checks the link in both
   directions.
5. Each property has exactly one broad canonical Hypothesis proof and exactly
   one falsifying canary. The proof guard resolves imported symbols to exact
   manifest targets: a same-named function from another module, a constructor
   without the targeted `__call__`, or unrelated code cannot satisfy the link.
   The canary demonstrates that the oracle can reject a plausible bad state,
   preventing trivially true properties from satisfying the gate.
6. History-dependent protocols use one literal local Hypothesis
   `RuleBasedStateMachine` and a small reference predicate. Evidence is scoped
   to initialization, stateful entry methods, and helpers reachable from them;
   dead methods and neighboring tests do not count. The reference create-item
   workflow proves new, duplicate, and conflicting idempotency-key sequences.
7. Every contracted public function or method in the proof surface is an
   explicit CrossHair target. The guard rejects a contract that omits symbolic
   evidence. Keeping the core pure and deterministic makes that closed rule
   practical; class invariants remain covered by construction, Hypothesis, and
   falsifying canaries. CrossHair is bounded in daily and CI lanes and receives
   a larger budget only through `just prove-deep`.
8. Domain entities, values, and events are frozen. Transformations live in
   small pure decision functions. Time, IDs, persistence, GitHub, MCP, CLIs,
   subprocesses, and other effects remain in an imperative shell behind ports.

The feedback lanes are intentionally different:

- `just prove`: static proof closure, bounded Hypothesis evidence, bounded
  CrossHair analysis;
- `just check`: the canonical full gate, including proof closure, CI-bounded
  symbolic analysis, and all tests;
- `just prove-deep`: a larger generated and symbolic search for risky changes,
  incidents, and scheduled CI.

This design does not claim complete mathematical verification of external
systems. It proves or searches the deterministic core under explicit
assumptions and tests the shell through examples, contracts, integration
scenarios, and fault cases.

## Alternatives considered

- **Coverage plus a pull-request checklist.** Rejected because both can be green
  while the safety property is absent.
- **Property tests without a catalog.** Rejected because a new critical symbol
  can still be added without a property, and tests can be misnamed or vacuous.
- **`icontract` alone.** Rejected because runtime contracts observe only
  executed examples and do not explore broad input or action spaces.
- **Hypothesis alone.** Rejected because the production code would not expose a
  stable machine-readable contract and pure targets would miss symbolic search.
- **CrossHair over the whole repository.** Rejected because effectful adapters
  create noise, unsupported state, and unpredictable latency.
- **Move the entire application to Rust, Dafny, or another proof-oriented
  language.** Rejected as the default: most integration value remains in
  Python, while a small pure core captures the useful proof boundary.

## Consequences

### Positive

- Agents cannot add domain behavior without naming the law and its evidence.
- A reviewer sees the property, implementation contract, generated proof,
  symbolic target, and counterexample in one diff.
- Pure decisions are reusable by application workflows and easy to replay.
- Symbolic analysis stays fast because the target list is explicit and small.
- Failures report stable property IDs rather than only test implementation
  names.

### Negative / cost accepted

- Every critical behavior requires a small amount of specification work before
  implementation.
- The same property may need a runtime contract, generator, and canary, although
  they share one oracle.
- CrossHair is bounded and may report no counterexample without constituting a
  proof over every Python behavior.
- Effects and availability assumptions remain outside the symbolic boundary.

### Risks and mitigations

- *Vacuous oracle:* every property has a falsifying canary and named failure
  modes.
- *Circular or misbound specification:* exact import resolution ties evidence
  to the declared oracle and target; oracles compare primitive input/output facts
  and do not call the implementation they judge.
- *Decorative stateful evidence:* only the executed local machine's stateful
  entry points and reachable helpers count; module-wide and dead-method calls do
  not.
- *Slow inner loop:* only proof-marked tests and the contracted function/method
  targets discovered through the manifest run in `just prove`, under small
  budgets. The architecture guard keeps those targets pure and small.
- *Property weakening to regain green:* property statements are normative;
  changing one is a design change reviewed with its counterexample and failure
  modes, not a test repair.
- *False confidence at external boundaries:* assumptions and port contracts
  remain explicit, and integration/fault tests continue to own effects.

## Validation

The reference slice contains:

- invariant contracts on values, entity state, and event state;
- pure create, rename, and event decisions with postconditions;
- generated constructor, invariant, model, and preservation proofs;
- one state-machine proof of idempotent retries;
- one falsifying canary for every catalog property;
- bounded CrossHair analysis of every pure decision target;
- guard tests that plant uncovered behavior, missing contracts, unknown IDs,
  missing Hypothesis evidence, missing canaries, coupled/non-boolean/effectful
  oracles, constructor-only or same-named target evidence, dead state-machine
  evidence, orphaned CrossHair targets, and contracted functions omitted from
  symbolic evidence.

The pack validates a generated project through the same `just check` command
that users and agents run.

## Migration and rollback

For an existing project, first inventory critical properties in `proof.toml`,
extract pure predicates, make core state immutable, then move transformations
behind pure decisions before attaching contracts and evidence. Do not add the
gate before the baseline catalog is complete.

Rollback requires removing the catalog, proof scripts, contracts, verification
harness, commands, dependency declarations, and this ADR together. Leaving
only the terminology would create a false guarantee.

## Removal / supersession criteria

Supersede this decision only with a mechanism that preserves all of these:
closed discovery of critical behavior, machine-readable production contracts,
generated and stateful evidence, non-vacuity witnesses, explicit symbolic
targets, and a bounded daily feedback loop.
