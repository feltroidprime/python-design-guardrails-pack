# ADR-0002: Repository control owns the shipped command surface

- Status: accepted
- Date: 2026-07-30
- Owners: repository maintainers
- Revisit trigger: a declared capability needs a separately versioned public
  command protocol

## Context and forces

N0 must be operable without inventing a product command. Agents still need a
machine-readable control surface for inspecting repository state and planning
the first capability.

## Decision

`python -m repoctl` is the only shipped command entry point. Its catalog and
process boundary live under `repoctl/modules/repository_generation/adapters/inbound/`.
It provides repository status, capability discovery, planning, application,
activation, retirement, derived-index generation, and proof reporting.

The shared declarations under `src/<package>/adapters/inbound/` are kept
minimal because repository control imports them. They define envelopes,
continuations, outcomes, and catalog data; they do not register a product CLI.

## Alternatives considered

- **A package-level application CLI.** Rejected: N0 has no product behavior
  to expose.
- **A free-form control script.** Rejected: repository operations need stable
  machine output and detached-process evidence.

## Consequences

### Positive

- A fresh repository has one clear command boundary.
- Product commands cannot appear before a capability declares and owns them.

### Negative / cost accepted

- Repository control is the only executable exemplar in N0.

### Risks and mitigations

- *Compatibility declarations grow into a generic framework:* retain only
  symbols imported by repository control; add future surface only with a real
  capability and an ADR.

## Validation

`tests/repoctl/contract/test_repoctl_cli_contract.py` exercises every control
command as a detached process. `tests/repoctl/integration/test_cli_queries.py`
checks its N0 query behavior, and `uv run lint-imports` enforces the package
boundary.

## Migration and rollback

New product command surfaces are added with their owning capability. N0 keeps
the control plane unchanged when no product capability exists.

## Removal / supersession criteria

Supersede this ADR if repository control is replaced by a different stable
automation boundary with equivalent process evidence.
