# ADR-0001: Foundation ports and reference adapters ship with the template

- Status: superseded
- Date: 2026-07-13
- Owners: repository maintainers
- Revisit trigger: the first real feature of this repository replaces the
  example slice, or a foundation brick stays unused after the domain has
  three or more aggregates

> Superseded by ADR-0007: the repository retires the committed Item example
> in favor of ownership zones and a self-hosting capability generator. This
> record stands as written below; only its status changed.

## Context and forces

Agents and humans code by imitating the surrounding repository. A template
whose example code is entirely throwaway teaches only throwaway shapes: the
first feature that needs the current time, an event reaction, or a real
database invents its own plumbing, and every later feature imitates that
invention instead of a designed one. At the same time, this repository's own
rules forbid speculative abstractions, and `AGENTS.md` requires an ADR for
any event bus or foundational abstraction. This ADR is that record.

## Decision

The generated repository ships one **replaceable example** (the `Item`
aggregate and its use cases) wired through **foundation bricks that are
meant to be kept**, each being the single reference exemplar of a
cross-cutting capability:

- **Time**: the application-owned `Clock` callable port
  (`application/ports.py`) with `adapters/outbound/system_clock.py` as the
  production implementation. Domain and application code never read the
  wall clock directly (the architecture guard already rejects it).
- **Identifiers**: the `ItemIdFactory` callable port with
  `adapters/outbound/uuid_ids.py`.
- **Domain events**: use cases publish already-happened facts through the
  `EventPublisher` protocol; `adapters/outbound/in_process_events.py`
  delivers them synchronously to handlers subscribed in the composition
  root. `adapters/outbound/audit_log.py` is the first independent consumer.
  This is deliberately not a framework: one list of dispatchers, no async,
  no persistence, no ordering guarantees beyond call order.
- **Persistence**: `adapters/outbound/sqlite_repository.py` is the
  reference outbound adapter — injected connection, driver errors
  translated into the application-owned `RepositoryError` with causes
  preserved, lifecycle owned by the composition root through a context
  manager (`bootstrap.sqlite_application`).
- **Port certification**: `tests/contract/item_repository_contract.py` is a
  reusable behavioral contract; every repository implementation subclasses
  it, which is what makes two implementations behind one port trustworthy
  (the Branch-by-Abstraction seam in its smallest honest form).
- **Entry point**: `python -m` runs the wired CLI (`__main__.py` →
  `bootstrap.main`), so there is exactly one demonstrated place where the
  production graph is composed.

Single-operation capabilities are callable `type` aliases; multi-operation
boundaries are `Protocol`s. New capabilities follow the nearest brick's
shape instead of inventing a parallel one.

## Alternatives considered

- **A bare toy slice only (previous state).** Rejected: it demonstrates the
  layer skeleton but leaves time, events, error translation, lifecycle, and
  port certification without an exemplar, so the first real feature
  improvises them.
- **A DI container or plugin framework.** Rejected: constructor injection
  from one composition root covers this repository's needs; a container is
  exactly the speculative framework the anti-slop rules forbid.
- **An async event bus with persistence/outbox.** Rejected: no consumer
  needs it; adopting one later is an ADR-worthy decision with real forces.

## Consequences

### Positive

- Every long-term pattern an agent must produce (inject time, publish an
  event, translate an external failure, certify a port, wire a resource
  lifecycle) has exactly one imitable exemplar that the quality gate keeps
  honest.
- The contract kit makes adding a real database a subclass-and-pass
  exercise instead of a design session.

### Negative / cost accepted

- The example application is no longer minimal (~15 small modules instead
  of ~8); readers must be told what to delete (the `Item` domain) and what
  to keep (the bricks).
- The in-process publisher's type-filtered `subscribe` is generic although
  only one event type exists yet; accepted as the cost of keeping handlers
  precisely typed.

### Risks and mitigations

- *Bricks ossify into a framework:* each brick stays one file with one
  reason to change; anything growing beyond that needs its own ADR.
- *The example database leaks into production decisions:* SQLite here is a
  reference implementation, not a recommendation; the first real
  persistence choice still deserves its own ADR.

## Validation

The shared contract tests certify both repository implementations; the
integration tests prove lifecycle (data survives reopening the database),
event delivery to the audit log, and CLI translation of domain errors into
exit codes. The full quality gate enforces layer direction over every brick.

## Migration and rollback

When the first real feature arrives: replace the `Item` aggregate, its use
cases, and the CLI verbs; keep the ports, the publisher, the clock, the id
factory, the contract kit, and the composition-root shape. Rolling back to
a bare slice means deleting the bricks and this ADR together.

## Removal / supersession criteria

Superseded brick by brick: e.g. adopting a real message broker replaces the
in-process publisher (new ADR), and the first production database adapter
may retire the SQLite reference once the contract kit certifies its
replacement.
