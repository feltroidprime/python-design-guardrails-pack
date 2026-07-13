# AGENTS.md — repository operating contract

Normative for every coding agent and human contributor. A change is complete only when `uv run python scripts/quality_gate.py` passes.

## Objective hierarchy

When goals conflict, the higher rule wins:

1. Preserve domain correctness and invariants.
2. Preserve dependency direction and explicit ownership.
3. Keep the smallest coherent design that satisfies the requirement.
4. Optimize readability for the next human reader.
5. Optimize speed only after the first four hold.

## Required workflow

Before editing:

1. Read the nearest `AGENTS.md`, `architecture.toml`, and relevant ADRs.
2. Identify the domain concept, use case, boundary, and reason to change.
3. Trace existing call paths and imports; extend an existing abstraction before creating a parallel one.
4. State which layer owns the change and why.

While editing:

1. Make the smallest vertical slice that proves the behavior.
2. Write or update tests with the production code.
3. Keep domain logic synchronous, deterministic, and framework-free.
4. Inject time, randomness, identifiers, persistence, network clients, and side effects through application-owned ports.
5. Run `just fix` after a coherent edit, not after every line.

Before claiming completion:

1. Run `uv run python scripts/quality_gate.py` to green.
2. Report the behavior changed, tests added, architecture impact, and remaining risks.
3. Never claim success over a failing or weakened gate; report the failure instead.

## Layer ownership

### `domain`

Owns business vocabulary, invariants, entities, aggregates, value objects, domain events, and domain errors.

- Depends only on the standard-library portions allowed by `architecture.toml`.
- Performs no I/O, environment reads, wall-clock reads, randomness/UUID generation, concurrency, logging, or framework imports.
- Rejects invalid states during construction or aggregate operations.
- Value objects and events are immutable, slotted, and keyword-only.

### `application`

Owns use cases, orchestration, commands/queries, and the ports those use cases require.

- May depend on `domain` only.
- Defines interfaces inward; never imports concrete adapters.
- Coordinates transactions and workflows; framework translation belongs to adapters.
- Prefer constructor injection; method injection only for operation-scoped dependencies.

### `adapters`

Owns translation to/from external systems and frameworks.

- `inbound` turns CLI/HTTP/jobs/messages into application calls.
- `outbound` implements persistence, messaging, clock, identifier, filesystem, and network ports.
- Translate external errors into stable application/domain errors, preserving causes.
- `inbound` and `outbound` never import each other.

### `bootstrap`

The composition root: the only ordinary location allowed to instantiate the production dependency graph. `__main__.py` only delegates to it.

## Foundation bricks: imitate, then extend

The example application separates two kinds of code (see ADR-0002):

- **Replaceable example**: the `Item` aggregate, its value objects, use cases, and CLI verbs. Replace them with the real domain; preserve the structure.
- **Foundation bricks**: exactly one reference exemplar per cross-cutting capability. Before writing new plumbing, imitate the matching brick:

| Need | Imitate |
|---|---|
| Current time | `Clock` port + `adapters/outbound/system_clock.py`; never read the clock in domain/application |
| New identifiers | `ItemIdFactory` port + `adapters/outbound/uuid_ids.py` |
| React to a domain fact | publish through `EventPublisher`; subscribe a handler in `bootstrap.build_application` (first consumer: `adapters/outbound/audit_log.py`) |
| Talk to an external system | `adapters/outbound/sqlite_repository.py`: injected resource, errors translated to the application-owned error with causes preserved |
| Resource lifecycle | `bootstrap.sqlite_application` context manager; acquire at the edge, release deterministically |
| Certify a port implementation | subclass the port's contract in `tests/contract/` (see `item_repository_contract.py`) and provide a `repository` fixture |
| New port | single operation → callable `type` alias; multiple operations → `Protocol` (both in `application/ports.py`) |

A cross-cutting need with no matching brick requires an ADR before the code exists.

## Architecture diagrams (derived, never drawn)

The LikeC4 model under `docs/architecture/likec4/generated/` is derived from the import-linter contracts and the real import graph (grimp). See `docs/adr/0001-derived-architecture-diagrams.md`.

- Never edit files under `docs/architecture/likec4/generated/`; when the gate's `diagram sync` check fails, run `just fix` (or `uv run python -m scripts.sync_architecture_diagrams --write`).
- Declare layers in exactly one place: the import-linter `layers` contract in `pyproject.toml`. Adding a layer there updates the linter and the diagrams simultaneously.
- Put hand-written views in `docs/architecture/likec4/views.c4` (never regenerated). The gate's `diagram views` check validates them against the generated model, so renaming or deleting a module moves the views in the same commit. Extend `specification.c4` only deliberately.
- The LikeC4 CLI version is pinned in exactly one place, `[tool.likec4]` in `pyproject.toml`; every invocation goes through `bunx likec4@<version>` (Bun is a toolchain prerequisite). Do not introduce `package.json`, JavaScript lockfiles, or `node_modules`. A version bump moves that single pin and must pass the full gate.
- To reason from the current architecture, browse `just diagrams` or query the LikeC4 model instead of trusting stale prose.

## Typing policy

- Python target is exactly 3.14.x.
- Every function and method is fully typed.
- `Any`, implicit unknowns, blanket `type: ignore`, and unparameterized generics are forbidden.
- Use `Protocol` for structural ports and callable strategies; use an ABC only when runtime inheritance semantics or shared implementation are genuinely required.
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

Admit a pattern only as a response to a named force, never as decoration:

- **Strategy:** name the behavior that varies independently. Prefer a function or callable protocol.
- **Adapter:** name the external API/framework being isolated.
- **Facade:** name the unstable or complex subsystem hidden behind a narrow stable API.
- **Repository:** name the aggregate persistence boundary; do not expose ORM/query-builder details inward.
- **Domain event:** name the already-completed domain fact and the independent consumers. Do not use events to hide a direct call.
- **Decorator:** use for transparent call-level augmentation.
- **Proxy:** use when access, lifecycle, identity, or remote substitution belongs to an object boundary.
- **Null object:** name the collaborator whose absence means "do nothing"; implement its port with a no-op and inject it in `bootstrap` instead of passing `port | None`.
- **State machine:** use only when legal transitions and transition-triggered behavior are first-class domain constraints.

A new foundational abstraction, framework, event bus, DI container, plugin system, or cross-layer dependency requires an ADR; record it using `docs/architecture/PATTERN_ADMISSION.md`.

## Error policy

- Raise the narrowest meaningful exception.
- Catch only where recovery, translation, cleanup, or added context occurs — never merely to log and continue.
- Preserve causes with `raise ... from error`.
- For a failure callers must distinguish, raise a domain exception instead of returning `None` (see "None discipline"). Result/Either types are not this repository's idiom; adopting one requires an ADR.

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
- No mutable module-level singletons, service locators, or fire-and-forget tasks.
- Use structured concurrency (`TaskGroup`) and explicit timeout/cancellation behavior at outer boundaries.
- Acquire resources with context managers and test cleanup on failure.
- Free-threaded Python does not make shared mutable state safe by design.

## Testing policy

- Test externally observable behavior and invariants, not private implementation details.
- Domain invariants receive example tests, plus property-based tests where the input space matters.
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
