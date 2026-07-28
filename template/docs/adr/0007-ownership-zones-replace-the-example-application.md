# ADR-0007: Ownership zones and the capability contract replace the example application

- Status: accepted
- Date: 2026-07-28
- Owners: repository maintainers
- Supersedes: ADR-0001
- Revisit trigger: the recursive N0 → N1 → N2 acceptance test first passes,
  or the four-zone ownership model needs a fifth zone or a different
  disjointness rule

## Context and forces

Item's problem was never its name. It threads through the use cases, the
ports, the bootstrap, the CLI catalog, and `proof.toml` — every long-term
exemplar ADR-0001 chose to keep lives partly inside it. Removing it
piecemeal means a horizontal refactor of the whole repository each time,
which is why it was never removed.

The deeper problem is what ADR-0001 asked Item to do: be simultaneously a
throwaway teaching example and the template's only ownership boundary.
Agents and humans still imitate the surrounding repository — ADR-0001's own
rationale, and it still holds — but a single fixed domain can only
demonstrate one application shape. This repository must support a pure
library, a CLI, an HTTP service, a worker, a pipeline, an external
integration, or a multi-agent orchestrator through composition, not through
one hardcoded example the user is expected to delete. And as the repository
accumulates real product code, "foundation" and "product" stop being a
convention a reviewer remembers and become a boundary that must hold by
construction: a scaffold update, or the repository's own generator, must be
provably unable to overwrite a file the user already owns.

Nothing in the current template states that boundary as data, and nothing
checks it. `docs/architecture/SPEC-0001.md` is the specification that
answers both forces at once: retire the single committed example in favor
of a self-hosting generator, and make the foundation/product boundary a
mechanically classified, gate-checked property of every path rather than a
documented expectation.

## Decision

The repository adopts `docs/architecture/SPEC-0001.md` as its normative
target and, with it, two structural commitments:

1. Every repository path belongs to exactly one of four disjoint ownership
   zones — FOUNDATION, PRODUCT, DERIVED, DECLARATION — decided by a pure
   classifier and enforced by a gate that fails on an overlapping root or an
   unclassified tracked path. No operation may write an existing PRODUCT
   file.
2. Every capability, whether it belongs to the repository's own control
   plane or to the user's product, satisfies one structural contract:
   required `domain`/`application`/`adapters` layering, hexagonal
   dependency direction, and an `api.py`-only public surface. One validator
   checks both, parameterized only by root and ownership, never by a weaker
   rule set for the repository's own generator.

This supersedes ADR-0001's premise that a single committed example
application is the repository's permanent teaching exemplar. The
repository's own capability generator becomes that permanent exemplar
instead: a system capability that must pass the same structural, proof, and
CLI contracts it will one day apply to generate product capabilities.

The migration lands in independently reviewable stages. This stage —
ownership zones, the disjointness guard, the shared capability structural
validator, and the guarantee that the template itself can never seed a
PRODUCT-rooted file — lands first and requires no change to Item. Capability
planning, application, activation, and the agent-native control-plane CLI
are specified but not yet built; Item is retained until a later stage makes
it redundant, not deleted ahead of its replacement.

## Alternatives considered

- **Keep Item as the permanent exemplar (status quo, ADR-0001).** Rejected:
  a single fixed domain cannot demonstrate every application shape this
  repository must support, and Item's structural reach is exactly what
  makes it something no one can afford to remove later either.
- **Delete Item immediately with no replacement exemplar.** Rejected: it
  would remove the imitable pattern ADR-0001 correctly identified agents
  need, and replace it with nothing.
- **Document the foundation/product boundary as a convention instead of
  classifying it mechanically.** Rejected for the same reason this pack
  rejects every convention-only invariant: it survives exactly until
  someone forgets it, and "foundation must never write product" is exactly
  the kind of coupling this pack insists on deriving or gating rather than
  trusting to memory.
- **Give the repository's own generator a relaxed rule set because it is
  infrastructure, not product.** Rejected: an exemption for the tool that
  builds the tool is the exemption most likely to be copied by every
  capability that follows it.

## Consequences

### Positive

- A foundation update's inability to touch product code becomes something
  the gate proves, not something the changelog promises.
- The repository supports any application shape the specification lists,
  through composition, instead of committing to one domain shape up front.
- The repository's own generator is dogfooded by exactly the rules it will
  enforce on what it generates; there is no separate, more lenient standard
  for infrastructure.

### Negative / cost accepted

- A freshly generated N0 is less immediately demonstrative than a working
  Item slice: there is no running example to point at until the first real
  capability exists.
- Every future file addition now answers to a permanent
  ownership-classification layer that did not exist before.
- The migration spans multiple independently landed pieces of work; Item
  and the ownership-zone machinery coexist until capability generation
  makes Item redundant, a wider window than a single-PR cutover.

### Risks and mitigations

- *A foundation update targets a product path.* The ownership-zone guard
  fails the gate on any overlapping root or unclassified tracked path.
- *The template itself accidentally seeds a file under a PRODUCT root.* A
  dedicated pack test fails the pack's own suite before that ships,
  independent of the generated repository's own gate.
- *A future capability — system or product — gets a structurally weaker
  validator.* The capability validator is one parameterized implementation,
  and a test fails if any rule is disabled, softened, or skipped for the
  system root.
- *The migration stalls partway and leaves an inconsistent repository.*
  Each stage keeps the full quality gate green on its own and retains Item
  unchanged until the stage that replaces it; nothing already landed
  depends on a future stage landing to remain correct.

## Validation

The ownership-zone guard exits non-zero when two ownership roots overlap or
when a tracked path resolves to no zone, and exits zero with the count of
classified paths otherwise. The capability validator is invoked with
different root and ownership parameters and a test asserts both invocations
resolve to the same rule identifier set, with a further test failing if any
rule is disabled, softened, or skipped for a system capability root. The
template product-root guard fails the pack's own test suite the moment a
template-owned path would render into a PRODUCT root. A synthetic
foundation-version update over a repository whose seeded product files were
all hand-modified leaves every one of those files byte-identical.

## Migration and rollback

Ownership zones, the disjointness guard, the shared capability structural
validator, and the product-root guard land first, alongside
`docs/architecture/SPEC-0001.md` and this ADR; Item is retained unchanged
through this stage, and no capability-generation behavior exists yet.

Later, independently reviewed stages add: the pure repository planner and
its proof evidence; the agent-native plan/apply control-plane CLI;
derived-index compilation and activation; and finally the removal of Item
and every mechanism — SQLite, event publishing, the clock, generated
identifiers — that existed only to give Item something to demonstrate.
Anything the repository's own control plane still needs from that list is
kept on as a real port, not example scaffolding.

Rolling back before Item's removal means keeping Item and deleting the
ownership-zone machinery this ADR adds. Rolling back after Item's removal
means restoring it from history; the ownership invariant this ADR adopts
guarantees that nothing landed in between silently overwrote a product
file, so that restoration is exact.

## Removal / supersession criteria

Supersede this decision only with a mechanism that preserves all of: a
mechanical, gate-checked classification of every repository path into
disjoint ownership classes; one structural contract shared identically by
system and product capabilities; and a proof that a foundation update
cannot silently modify product code.
