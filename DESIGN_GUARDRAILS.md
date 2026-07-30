# Design concerns → deterministic repository controls

## Scope

This document maps software-design concerns to Python 3.14 techniques and the
concrete controls shipped by this pack. It distinguishes mechanically
observable rules from decisions that still require engineering judgment.

Rows that cite the generated `AGENTS.md` describe the default `full` agent
contract; `agents_contract` may remove it or switch it to hooks-first
verification. The prek commit and pre-push hooks are unconditional in
standalone repositories. Deterministic architecture, documentation, type,
lint, and test controls remain available through the justfile and quality
gate regardless.

The pack root has a separate maintainer feedback loop because it is a
lock-free generator rather than a generated application. Its Ruff policy
shares the generated rule floor and formatting choices, while explicit
root-only exceptions cover the generator's subprocess and CLI boundaries.
Pre-commit proves fast rendering and policy coherence; pre-push runs the
complete root suite with four work-stealing workers under a one-minute
interaction budget. The slower downstream generation, symbolic, repair,
worktree, and synthetic foundation-update ownership-preservation checks remain
mandatory through `just validate` at completion and in CI. The pack exposes no
public Copier update command; a future versioned repository-update protocol
will own foundation migrations.

## Code-level design

| Design concern | Python 3.14 approach | Deterministic materialization |
|---|---|---|
| Coupling, cohesion, SRP, DRY, KISS, YAGNI in context | modules organized by reason to change; small functions; no speculative abstractions | a 650-line production-module ceiling keeps cohesive policy and gate logic together without forcing artificial splits; tests retain a 500-line ceiling, functions 60, and classes 250; Ruff cyclomatic complexity (`C901`, max 10), forbidden dumping-ground modules, and the pattern admission checklist keep the larger module budget from becoming a god-object waiver |
| Law of Demeter | expose intention-revealing operations rather than object-navigation chains | architecture guard ceilings plus review rule in `AGENTS.md`; tests at public boundaries |
| Strategy emerging naturally | function, callable `Protocol`, or injected strategy only when behavior varies | no mandatory Strategy base class; ADR/checklist requires a named variation axis |
| Composition over inheritance | constructor injection; `Protocol`; shallow inheritance only for true substitutability | agents must inject dependencies; BasedPyright validates structural contracts; ARCH030 requires `@override` for resolved in-repository base methods |
| Strategy, Adapter, Facade | callable strategies; adapters around I/O/frameworks; narrow stable public API | adapters isolated by import contracts; `__all__` public surfaces; pattern admission record |
| Ports & Adapters | application-owned ports and outer implementations | Import Linter layer contract; inbound/outbound adapter independence; domain purity guard |
| Domain invariants | immutable value objects and pure transitions with named pre/postconditions | frozen/slotted core state; one `proof/policy.toml` declares source/test roots for both the product package and `repoctl`, and its ownership-zone catalogs close the public proof surface and aggregate its property declarations into one catalog index; CrossHair derives its import path from that policy data and receives a reliable minimum canary budget; independent predicates feed `icontract`, Hypothesis proofs, one falsifying canary per declared oracle (PROOF021/PROOF028 reject a canary that conjoins two oracles, because such a conjunction stays false when either operand degenerates to `return True`), and mandatory CrossHair targets for contracted functions and methods; the CrossHair gate reports each target's status under its property ID and fails unless it also refutes `verification/harness/symbolic_canary.py`, a deliberately false contract over the domain value types that turns an unexplored symbolic run from a silent pass into a failure; a contract condition may be an inline `lambda` or a named module-level function (the guard follows the named condition to its oracle, and the named form keeps the condition fully type-checked); focused verification-only `-m stateful` runs skip product coverage because they exercise the independent proof model rather than product code, while the full quality gate retains the 90% product coverage floor; ARCH027 rejects exact same-named Enum copies and ARCH029 rejects used domain aliases to bare primitives |
| Derived repository indexes | pure canonical projection from explicit declarations | `REPOCTL::DERIVED-INDEX-EXACT` links `compile_indexes` to an independent oracle, mixed-lifecycle Hypothesis evidence, and CrossHair; the compiler filters exactly active declarations, deduplicates and orders its immutable output, emits stable JSON bytes, and a source test rejects runtime discovery imports |
| Repository boundaries | repository `Protocol` defined inward, implementation outward | application ports package plus a reusable contract-test kit (`tests/contract/`) certifying both shipped implementations (memory, SQLite) |
| Fail fast at correct boundary | domain raises domain errors; adapters translate external failures | blanket catches forbidden; exception chaining and narrow handling enforced by Ruff; the SQLite reference adapter translates driver errors into the application-owned `RepositoryError` |
| None at the edge, strict core | better defaults over `Optional`; parse raw data into strict domain types at the boundary; explicit state types; null objects over `port \| None` | "None discipline" decision ladder in the template `AGENTS.md`, enforced by guard rules ARCH016–ARCH018 |
| Primitive obsession: paths | `pathlib.Path` from first touch; `str` paths are wire data parsed at the adapter edge and serialized only in the final external call | "Path discipline" decision ladder in the template `AGENTS.md`; Ruff `PTH` rejects the `os.path` API; ARCH019–ARCH020 reject token-named `str` declarations and ARCH028 rejects untokenized `str` declarations used directly as paths |
| Agent-native CLI boundaries | ordinary typed arguments; explicit stdin policy; versioned envelopes and outcomes; progressive help; bounded composable queries; conditional idempotency; closed safety variants | closed `CommandSpec` catalog drives argparse and machine-readable `capabilities`; exact input/filter/field/shared-outcome cases plus concurrent shared port contracts prove behavior at detached and open-stdin process seams; ARCH021–ARCH025 reject prompt drift, uncontrolled exits, framework leakage, catalog bypass, and removal of argument-primary input |
| Agent-session evidence | stable facade over a commit-pinned private module; raw-first deterministic normalization | `just session-log` invokes `session-profiler-optimizer`, whose Harbor 0.18.0 boundary converts one immutable Claude Code or Codex JSONL snapshot to ATIF-v1.7 plus private TSV/route/blob/manifest evidence; per-source call/result identities and hashes fail closed on loss; opt-in `just session-e2e` samples five local size quantiles per agent |
| AI-generated structural problems | explicit scope, minimal diffs, no parallel abstractions, proof via gate | `AGENTS.md` requires property scope, assumptions, and counterexample before implementation; `just prove-one` is the fast law-specific loop and `just check` is the acceptance route |

## Boundary and system design

| Design concern | Python 3.14 approach | Deterministic materialization |
|---|---|---|
| Classes vs simple functions | functions for stateless transformations; classes for state, polymorphism, identity, or lifecycle | class admission questions in `AGENTS.md`; complexity ceilings discourage god objects |
| Strategies and higher-order functions | `Callable`, generic callables, closures, `Protocol.__call__` | strict typing and examples; avoid framework DI containers by default |
| Protocols and ABCs | `Protocol` for structural ports; ABC only for shared runtime semantics | port package convention; `@override` required when inheritance is used |
| Generators and streaming | `Iterator`, `Iterable`, generators; no eager materialization without reason | explicit streaming policy; review rule in `AGENTS.md` (Ruff's `PERF` micro-optimizations are deliberately not selected) |
| Bounded automation output | positive default/maximum page sizes, stable ordering, continuation tokens, explicit stream termination and bulk scope | query case variants seed beyond the default and follow continuations; repository ports receive the bound; streaming and bulk case variants require filters/termination or scope/destination before a command can enter the catalog |
| Global coupling and shared state | explicit ownership; immutable configuration; injected clock/RNG/clients | ARCH026 rejects mutable module-level container state; domain wall-clock/random/UUID calls are rejected; `Clock`/`ItemIdFactory` ports are the injected exemplars |
| Error handling | small domain exception taxonomy; translate at boundaries; preserve causes | blind/bare catches rejected; exception messages and chaining checked |
| Stable process failures | coarse exit classes plus fine-grained machine codes, retryability, and corrective hints; debug tracebacks opt-in | protocol `1.0` sends success only to stdout and failures only to stderr; universal process cases reject tracebacks and ANSI by default; breaking schema/exit changes require a versioned ADR |
| Modules and folders around boundaries | package-by-boundary rather than technical dumping grounds | fixed layer skeleton, import contracts, generic module-name ban; `__init__.py` must carry a public surface or ownership docstring (empty ones rejected, none allowed under `tests/`) |
| Foundation vs. product ownership across the whole repository tree | every path resolves to exactly one of four disjoint zones (FOUNDATION, PRODUCT, DERIVED, DECLARATION) through one pure repository-generation classifier; capability roots share one structural contract whether they belong to the generator or the product | `scripts/ownership.py` only adapts filesystem-shaped policy values to the classifier and contains no second rule table; named errors reject absolute paths, parent escapes, empty segments, and non-canonical Unicode; `REPOCTL::PLAN-PATH-CLOSED` links successful classification to an independent oracle, Hypothesis, icontract, and CrossHair; the ownership-zone guard fails the gate on an overlapping root, changed four-zone vocabulary, or unclassified tracked path; the template product-root guard fails the pack's own test suite if a template-owned path would render into a PRODUCT root; the capability validator enforces required structure, layer direction (including the standard-library-and-`icontract`-only domain import allowlist), and the `api.py`-only public surface identically for a system and a product capability root, with no rule weakened for the system root (ADR-0007) |
| Inspectable repository plans | frozen, slotted, keyword-only intent/snapshot/operation/plan values; ownership roots and prior digests as explicit snapshot data; normalized input ordering; canonical UTF-8 JSON; SHA-256 content identity | `REPOCTL::PLAN-DETERMINISTIC` links pure `plan(snapshot, intent)` to an independent repeat-equality oracle, 0–100-capability Hypothesis snapshots, and CrossHair; PRODUCT seeds are create-only, declaration and derived writes carry exact prior-digest preconditions, and operation targets equal the planner's intended target set; the control CLI may persist an inspected plan only through the repository port in its reserved plan-control directory, whose artifacts stay readable but are excluded from planning snapshots so saving a plan cannot make it stale; applying that plan uses the durable transaction protocol and replays as `already_applied`; ARCH011 limits repository-generation domain and application imports to separate closed pure-module allowlists, including pure `keyword` for language-defined identifier validation, while ARCH012 rejects ambient calls in both layers, with `os`/`open` and `shutil.copyfile` mutation canaries; existing value invariants reject invalid schema, digest, precondition, content, and repository-relative-path state, while ARCH006/ARCH007 keep immutability structural |
| Async and concurrency outside domain | sync domain; async orchestration in adapters/application edge | `async def` rejected in domain; concurrency imports rejected there |
| Event-driven decoupling | immutable typed events; handlers as callables; events used across real workflow boundaries | event modules must contain frozen/slotted/keyword-only dataclasses; `EventPublisher` port + in-process publisher with a real subscribed consumer (ADR-0001); event adoption checklist |
| Build vs buy | dependency decision includes maintenance, lockfile, replacement boundary | ADR required for foundational dependency; `uv.lock --check`; dependency audit workflow |

## Evolution and governance

| Design concern | Python 3.14 approach | Deterministic materialization |
|---|---|---|
| Context managers | `contextmanager`, `ExitStack`, `AsyncExitStack` for lifecycle guarantees | lifecycle resources must be acquired at edges and tested for cleanup; `bootstrap.sqlite_application` is the shipped exemplar (integration test reopens the database) |
| Decorator vs Proxy | decorator for call-level augmentation; proxy for object-level substitution/control | pattern admission matrix in architecture docs |
| Async failure containment | `TaskGroup`, cancellation discipline, timeout boundaries, exception groups | concurrency checklist; no fire-and-forget tasks; integration tests for cancellation |
| Generic composable engines | Python 3.12+ type-parameter syntax and constrained generic protocols | BasedPyright strict generics; no unbound/dynamic type parameters |
| Change amplification | stable ports, narrow public API, contract tests, characterization tests | import fitness functions, public surface rules, change-impact section in PR template |
| Strangler Pattern | old/new implementations behind one port, traffic or call-path migration | migration ADR template with coexistence, rollback, telemetry, and deletion criteria |
| Branch by Abstraction | introduce seam, dual implementation, switch, remove old path | dedicated migration checklist and expiring exception ledger |
| Prevent architectural drift | fitness functions executed locally and in CI | `just check` parses every tracked Python file before repairs, then runs the AST guard + Import Linter + strict type/lint/test gate |
| Local enforcement from repository creation onward | bootstrap before the first commit; use Git's shared hooks directory for linked worktrees | `python-repo init` runs `just bootstrap` after `git init` and before the baseline commit; every `just check` inspects the shared prek shims and repairs missing or invalid shims with `uv run prek install -f`; pack validation deletes and repairs both shims and proves linked-worktree sharing |
| Fast, coherent pack maintenance | provision root tools ephemerally; share lint/format policy with generated repositories; separate interactive and canonical validation budgets | root `pyproject.toml` owns the shared Ruff policy and root-only boundary exceptions, while the root justfile provisions the common version floor; `just check` deterministically repairs then verifies `instantiate.py`, `scripts`, `tests`, and `template`; coherence tests compare the root/generated Ruff floors and hook routing; pre-commit runs the focused policy suite, pre-push runs all root tests with four work-stealing workers below one minute, and CI plus completion retain the full `just validate` downstream matrix |
| Pre-deployment repository readiness | bounded local checks with explicit skip semantics for unavailable external state | `just doctor` reports stable hook, working-tree, default-branch/origin, `gh auth`, `uv sync --check`, and Python-version statuses plus a verdict in under five seconds; only absent/offline external checks warn, while any failure returns non-zero |
| Documentation that stays true | one owner per fact; freshness ladder (derived > checked > dated); registry with admission rule | documentation map (`docs/README.md`) + docs guard (DOC001–DOC007): broken path references, dangling `ARCH-EXCEPTION` markers, malformed or non-contiguous ADRs, and unregistered documents fail the gate |
| Invariants entrusted to human memory | derive coupled values from their source of truth, or enforce the coupling with a test or gate check — never with a comment asking a future editor to remember | ARCH031 rejects reminder comments that schedule manual upkeep ("bump this after each release", "keep in sync with"); the pack's own update round-trip derives its candidate tag from the clone's real tags instead of a manually bumped constant; `tests/test_pin_coherence.py` discovers every multi-location version pin by scanning the tracked tree so no document enumerates locations; a Claude Code `PostToolUse` hook (`scripts/reminder_comment_hook.py`) rejects reminder comments at edit time, before they ever reach the tree |
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
