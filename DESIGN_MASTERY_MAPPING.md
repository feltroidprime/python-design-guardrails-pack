# Software Design Mastery → deterministic repository controls

## Epistemic status

The public page describes a program launching in 2026 and exposes a detailed curriculum, but not the lessons themselves. The first column below is explicit. The probable Python techniques are informed inference from the curriculum and ArjanCodes' public teaching. The final column is this pack's independent enforcement design.

Rows that cite the generated `AGENTS.md` or Git hooks describe the default
`full`/`precommit = true` materialization. The named benchmark ablations may
remove the agent contract, switch it to hooks-first verification, or omit the
hook configuration; deterministic architecture, documentation, type, lint,
and test controls remain available through the justfile and quality gate.

## Core Designer

| Public topic | Probable Python 3.14 technique | Deterministic materialization |
|---|---|---|
| Coupling, cohesion, SRP, DRY, KISS, YAGNI in context | modules organized by reason to change; small functions; no speculative abstractions | module/function/class ceilings; Ruff complexity rules; forbidden dumping-ground modules; pattern admission checklist |
| Law of Demeter | expose intention-revealing operations rather than object-navigation chains | Ruff design rules plus review rule in `AGENTS.md`; tests at public boundaries |
| Strategy emerging naturally | function, callable `Protocol`, or injected strategy only when behavior varies | no mandatory Strategy base class; ADR/checklist requires a named variation axis |
| Composition over inheritance | constructor injection; `Protocol`; shallow inheritance only for true substitutability | agents must inject dependencies; BasedPyright validates structural contracts; inheritance requires justification |
| Strategy, Adapter, Facade | callable strategies; adapters around I/O/frameworks; narrow stable public API | adapters isolated by import contracts; `__all__` public surfaces; pattern admission record |
| Ports & Adapters | application-owned ports and outer implementations | Import Linter layer contract; inbound/outbound adapter independence; domain purity guard |
| Domain invariants | value objects and aggregate methods; invalid construction rejected | frozen/slotted value-object modules; property tests; no raw primitive obsession at boundaries |
| Repository boundaries | repository `Protocol` defined inward, implementation outward | application ports package plus a reusable contract-test kit (`tests/contract/`) certifying both shipped implementations (memory, SQLite) |
| Fail fast at correct boundary | domain raises domain errors; adapters translate external failures | blanket catches forbidden; exception chaining and narrow handling enforced by Ruff; the SQLite reference adapter translates driver errors into the application-owned `RepositoryError` |
| None at the edge, strict core | better defaults over `Optional`; parse raw data into strict domain types at the boundary; explicit state types; null objects over `port \| None` | "None discipline" decision ladder in the template `AGENTS.md`, enforced by guard rules ARCH016–ARCH018 |
| Primitive obsession: paths | `pathlib.Path` from first touch; `str` paths are wire data parsed at the adapter edge and serialized only in the final external call | "Path discipline" decision ladder in the template `AGENTS.md`; Ruff `PTH` rejects the `os.path` API; guard rules ARCH019–ARCH020 reject path-named `str` declarations, letting BasedPyright propagate `Path` to every caller |
| AI-generated structural problems | explicit scope, minimal diffs, no parallel abstractions, proof via gate | `AGENTS.md` workflow; one quality command; no completion claim without evidence |

## System Designer

| Public topic | Probable Python 3.14 technique | Deterministic materialization |
|---|---|---|
| Classes vs simple functions | functions for stateless transformations; classes for state, polymorphism, identity, or lifecycle | class admission questions in `AGENTS.md`; complexity ceilings discourage god objects |
| Strategies and higher-order functions | `Callable`, generic callables, closures, `Protocol.__call__` | strict typing and examples; avoid framework DI containers by default |
| Protocols and ABCs | `Protocol` for structural ports; ABC only for shared runtime semantics | port package convention; `@override` required when inheritance is used |
| Generators and streaming | `Iterator`, `Iterable`, generators; no eager materialization without reason | Ruff performance rules; explicit streaming policy |
| Global coupling and shared state | explicit ownership; immutable configuration; injected clock/RNG/clients | mutable module globals rejected; domain wall-clock/random/UUID calls rejected; `Clock`/`ItemIdFactory` ports with outer adapters as the injected exemplars |
| Error handling | small domain exception taxonomy; translate at boundaries; preserve causes | blind/bare catches rejected; exception messages and chaining checked |
| Modules and folders around boundaries | package-by-boundary rather than technical dumping grounds | fixed layer skeleton, import contracts, generic module-name ban; `__init__.py` must carry a public surface or ownership docstring (empty ones rejected, none allowed under `tests/`) |
| Async and concurrency outside domain | sync domain; async orchestration in adapters/application edge | `async def` rejected in domain; concurrency imports rejected there |
| Event-driven decoupling | immutable typed events; handlers as callables; events used across real workflow boundaries | event modules must contain frozen/slotted/keyword-only dataclasses; `EventPublisher` port + in-process publisher with a real subscribed consumer (ADR-0002); event adoption checklist |
| Build vs buy | dependency decision includes maintenance, lockfile, replacement boundary | ADR required for foundational dependency; `uv.lock --check`; dependency audit workflow |

## Master Designer

| Public topic | Probable Python 3.14 technique | Deterministic materialization |
|---|---|---|
| Context managers | `contextmanager`, `ExitStack`, `AsyncExitStack` for lifecycle guarantees | lifecycle resources must be acquired at edges and tested for cleanup; `bootstrap.sqlite_application` is the shipped exemplar (integration test reopens the database) |
| Decorator vs Proxy | decorator for call-level augmentation; proxy for object-level substitution/control | pattern admission matrix in architecture docs |
| Async failure containment | `TaskGroup`, cancellation discipline, timeout boundaries, exception groups | concurrency checklist; no fire-and-forget tasks; integration tests for cancellation |
| Generic composable engines | Python 3.12+ type-parameter syntax and constrained generic protocols | BasedPyright strict generics; no unbound/dynamic type parameters |
| Change amplification | stable ports, narrow public API, contract tests, characterization tests | import fitness functions, public surface rules, change-impact section in PR template |
| Strangler Pattern | old/new implementations behind one port, traffic or call-path migration | migration ADR template with coexistence, rollback, telemetry, and deletion criteria |
| Branch by Abstraction | introduce seam, dual implementation, switch, remove old path | dedicated migration checklist and expiring exception ledger |
| Prevent architectural drift | fitness functions executed locally and in CI | AST guard + Import Linter + strict type/lint/test gate |
| Architecture communication without drift | diagrams derived from the code, not drawn | LikeC4 model generated from the grimp import graph (same library Import Linter uses); gate fails on model drift and on views referencing missing elements; free-form views stay team-owned |
| Documentation that stays true | one owner per fact; freshness ladder (derived > checked > dated); registry with admission rule | documentation map (`docs/README.md`) + docs guard (DOC001–DOC007): broken path references, dangling `ARCH-EXCEPTION` markers, malformed or non-contiguous ADRs, and unregistered documents fail the gate |
| Trade-offs under pressure | ADR with forces, rejected options, cost, revisit trigger | mandatory ADR triggers and explicit exception expiry |
| AI speed vs long-term risk | AI proposes; deterministic tools and humans retain design authority | agent contract forbids architecture invention without evidence and requires gate output |

## Python 3.14-specific stance

- Use native deferred annotation evaluation. Do not add `from __future__ import annotations` in a 3.14-only repository.
- Use `type` aliases and modern type-parameter syntax when generics genuinely reduce duplication.
- Treat free-threaded Python as a reason to avoid implicit shared mutable state, not as permission to add threads.
- Keep concurrency and subinterpreters behind explicit application/adapters boundaries.
- Use template strings only through explicit renderers at trust boundaries; do not spread rendering concerns into the domain.

## What cannot be made fully deterministic

No linter can prove that a name reflects the domain, an abstraction is worthwhile, a trade-off is correct, or a class has exactly one reason to change. This pack therefore uses a hierarchy:

1. static enforcement where the property is mechanically observable;
2. architecture contracts where dependency direction is observable;
3. tests where behavior and invariants are observable;
4. ADR/checklist obligations where judgment is irreducible;
5. explicit, expiring exceptions rather than silent rule weakening.
