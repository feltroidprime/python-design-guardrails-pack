# AGENTS.md — repository operating contract

This file is normative for every coding agent and human contributor.

## Objective hierarchy

1. Preserve domain correctness and invariants.
2. Preserve dependency direction and explicit ownership.
3. Keep the smallest coherent design that satisfies the requirement.
4. Optimize readability for the next human reader.
5. Optimize speed only after the first four constraints hold.

A change is incomplete until `uv run python scripts/quality_gate.py` passes.

## Required workflow

Before editing:

1. Read the nearest `AGENTS.md`, `architecture.toml`, and relevant ADRs.
2. Identify the domain concept, use case, boundary, and reason to change.
3. Trace existing call paths and imports. Extend an existing abstraction before creating a parallel one.
4. State which layer owns the change and why.

During editing:

1. Make the smallest vertical slice that proves the behavior.
2. Write or update tests with the production code.
3. Keep domain logic synchronous, deterministic, and framework-free.
4. Inject time, randomness, identifiers, persistence, network clients, and side effects through application-owned ports.
5. Run `just fix` after a coherent edit, not after every line.

Before completion:

1. Run `uv run python scripts/quality_gate.py`.
2. Report the behavior changed, tests added, architecture impact, and remaining risks.
3. Never claim success while suppressing a failing gate.

## Layer ownership

### `domain`

Owns business vocabulary, invariants, entities, aggregates, value objects, domain events, and domain errors.

- May depend only on the standard library portions allowed by `architecture.toml`.
- Must not perform I/O, read environment variables, get wall-clock time, generate randomness/UUIDs, start concurrency, log, or know frameworks.
- Must reject invalid states during construction or aggregate operations.
- Value objects and events are immutable, slotted, and keyword-only.

### `application`

Owns use cases, orchestration, commands/queries, and ports required by those use cases.

- May depend on `domain`.
- Defines interfaces inward; never imports concrete adapters.
- Coordinates transactions and workflows but does not contain framework translation.
- Prefer constructor injection. Method injection is reserved for operation-scoped dependencies.

### `adapters`

Owns translation to/from external systems and frameworks.

- `inbound` turns CLI/HTTP/jobs/messages into application calls.
- `outbound` implements persistence, messaging, clock, identifier, filesystem, and network ports.
- Translate external errors into stable application/domain errors while preserving causes.
- Inbound and outbound adapters must not import each other.

### `bootstrap`

The composition root. It is the only ordinary location allowed to instantiate the production dependency graph. `__main__.py` only delegates to it.

## Foundation bricks: imitate, then extend

The example application separates two kinds of code (see ADR-0002):

- **Replaceable example**: the `Item` aggregate, its value objects, use cases, and CLI verbs. Replace them with the real domain; preserve the structure.
- **Foundation bricks to keep**: each cross-cutting capability has exactly one reference exemplar. Before writing new plumbing, imitate the brick:

| Need | Imitate |
|---|---|
| Current time | `Clock` port + `adapters/outbound/system_clock.py`; never read the clock in domain/application |
| New identifiers | `ItemIdFactory` port + `adapters/outbound/uuid_ids.py` |
| React to a domain fact | publish through `EventPublisher`; subscribe a handler in `bootstrap.build_application` (first consumer: `adapters/outbound/audit_log.py`) |
| Talk to an external system | `adapters/outbound/sqlite_repository.py`: injected resource, errors translated to the application-owned error with causes preserved |
| Resource lifecycle | `bootstrap.sqlite_application` context manager; acquire at the edge, release deterministically |
| Certify a port implementation | subclass the port's contract in `tests/contract/` (see `item_repository_contract.py`) and provide a `repository` fixture |
| New port | single operation → callable `type` alias; multiple operations → `Protocol` (both in `application/ports.py`) |

Every new implementation of an existing port must pass that port's shared contract test. A new cross-cutting brick (not listed above) requires an ADR before it exists.

## Architecture diagrams (derived, never drawn)

The LikeC4 model under `docs/architecture/likec4/generated/` is derived from
the import-linter contracts and the real import graph (grimp). See
`docs/adr/0001-derived-architecture-diagrams.md`.

- **Never edit files under `docs/architecture/likec4/generated/`.** The
  quality gate's `diagram sync` check fails on any drift; resolve it with
  `just fix` (or `uv run python -m scripts.sync_architecture_diagrams --write`).
- Layers are declared in exactly one place: the import-linter `layers`
  contract in `pyproject.toml`. Adding a layer there updates the linter and
  the diagrams simultaneously.
- Hand-written views belong in `docs/architecture/likec4/views.c4` (never
  regenerated). The gate's `diagram views` check validates them against the
  generated model, so renaming or deleting a module forces the views to move
  in the same commit. `specification.c4` is written once; extend it only
  deliberately.
- The LikeC4 CLI version is pinned in exactly one place, `[tool.likec4]` in
  `pyproject.toml`, and every invocation goes through `bunx likec4@<version>`
  (Bun is a toolchain prerequisite). Do not introduce `package.json`,
  JavaScript lockfiles, or `node_modules`. Version bumps move that single pin
  and must pass the full gate.
- To reason from the current architecture, browse it with `just diagrams` or
  query the model through LikeC4 tooling instead of trusting stale prose.

## Typing policy

- Python target is exactly 3.14.x.
- Every function and method is fully typed.
- `Any`, implicit unknowns, blanket `type: ignore`, and unparameterized generics are forbidden.
- Use `Protocol` for structural ports and callable strategies.
- Use an ABC only when runtime inheritance semantics or shared implementation are genuinely required.
- Mark actual overrides with `@override`.
- Model closed variants with enums or unions and exhaustive `match` statements.
- Prefer domain value objects to ambiguous primitives at important boundaries.
- Do not add `from __future__ import annotations`; Python 3.14 evaluates annotations lazily.

## Function-or-class decision

Start with a function. Introduce a class only when at least one is true:

- the concept has identity or protected mutable state;
- behavior varies behind a stable protocol;
- lifecycle/resource ownership must be guaranteed;
- multiple operations share a real invariant;
- the object is a domain entity, aggregate, value object, or adapter.

Do not create a class merely to namespace one function.

## Pattern admission rules

Patterns are responses to forces, not decorations.

- **Strategy:** name the behavior that varies independently. Prefer a function or callable protocol.
- **Adapter:** name the external API/framework being isolated.
- **Facade:** name the unstable or complex subsystem hidden behind a narrow stable API.
- **Repository:** name the aggregate persistence boundary; do not expose ORM/query-builder details inward.
- **Domain event:** name the already-completed domain fact and the independent consumers. Do not use events to hide a direct call.
- **Decorator:** use for transparent call-level augmentation.
- **Proxy:** use when access, lifecycle, identity, or remote substitution belongs to an object boundary.
- **Null object:** name the collaborator whose absence means "do nothing"; implement its port with a no-op and inject it in `bootstrap` instead of passing `port | None`.
- **State machine:** use only when legal transitions and transition-triggered behavior are first-class domain constraints.

A new foundational abstraction, framework, event bus, DI container, plugin system, or cross-layer dependency requires an ADR.

## Error policy

- Raise the narrowest meaningful exception.
- Validate domain invariants at construction/operation time.
- Catch only where recovery, translation, cleanup, or added context occurs.
- Preserve causes with `raise ... from error`.
- Never catch an exception merely to log and continue.
- Do not return `None` for a failure that callers must distinguish; use a domain exception (see "None discipline"). Result/Either types are not this repository's idiom; adopting one requires an ADR.

## None discipline

`None` is edge data, not domain vocabulary. Raw input (API payloads, sensor readings, argv) may be incomplete; the core must never inherit that uncertainty. Before typing `X | None`, apply the first matching rule:

1. **"Nothing" has a real value.** Prefer an empty collection, `0`, or `False` over `None` when the meaning is "nothing to do": `field(default_factory=tuple)`, never `list[X] | None = None` (ARCH016).
2. **Required data may be missing at the edge.** Parse, don't propagate: the adapter converts raw input into a strict domain object and raises at the boundary (fail fast). Optional fields belong to edge DTOs in `adapters`; domain models never carry them (ARCH017).
3. **The operation can fail.** Raise the narrowest domain exception instead of returning `None` (ARCH018 in domain).
4. **The object moves through lifecycle states with different guarantees.** One class accumulating optional fields is the warning sign. Model each state as its own frozen type (`DraftOrder` / `PaidOrder`, not `Order` with optional `paid_at`) and let each signature demand exactly the state it needs — invalid states become unrepresentable.
5. **A collaborator is optional and doing nothing is valid.** Inject a null object implementing the same port from `bootstrap`; do not thread `port | None` through call sites and re-check it everywhere.
6. **`None` is itself a legal value and "not provided" must be distinguished.** Use a dedicated module-level sentinel object, not a second meaning for `None`.
7. **A query may legitimately find nothing.** A port may return `X | None` (`ItemRepository.get` is the exemplar); the caller converts it into a domain exception or an explicit branch immediately. An optional never travels more than one call inward.

## State, concurrency, and lifecycle

- One owner for each mutable state.
- No mutable module-level singletons or service locators.
- No fire-and-forget tasks.
- Use structured concurrency (`TaskGroup`) and explicit timeout/cancellation behavior at outer boundaries.
- Acquire resources with context managers and test cleanup on failure.
- Free-threaded Python does not make shared mutable state safe by design.

## Testing policy

- Test externally observable behavior and invariants, not private implementation details.
- Domain invariants receive example tests and property-based tests where the input space matters.
- Every port implementation must pass the shared contract test for that port.
- Unit tests perform no network access; the test runner disables sockets by default.
- Integration tests are marked explicitly and still prefer local deterministic substitutes.
- A bug fix starts with a failing regression test.
- Coverage is a floor, not evidence of good assertions.

## Anti-slop rules

Forbidden without an ADR-backed exception:

- `utils.py`, `helpers.py`, `common.py`, or `misc.py` dumping grounds;
- `__init__.py` under `tests/` (test packages are namespace packages, ARCH014) and empty `__init__.py` anywhere (an `__init__.py` states its package's public surface or ownership, ARCH015);
- duplicated models for the same concept;
- `Manager`, `Handler`, `Processor`, or `Service` names without a precise domain qualifier;
- speculative generic frameworks for one implementation;
- hidden I/O in properties, constructors, or domain methods;
- boolean flags that switch unrelated behavior;
- `None` where "None discipline" prescribes a default, a parse, an exception, or a state (ARCH016–ARCH018);
- comments that restate code instead of explaining a non-obvious invariant or trade-off;
- broad refactors mixed into a feature change;
- weakening a gate to make generated code pass.

## Architecture exceptions

A suppression is legal only when it includes a narrow diagnostic code and an `ARCH-EXCEPTION: ADR-XXXX` marker. The referenced ADR must record owner, reason, scope, expiry/revisit trigger, and removal criteria.
