# Validation record — 2026-07-29

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, and pytest-xdist
3.8.0.

## Change validated

The first SPEC-0001 migration epic is complete:

- Generated repositories ship `.repo/repository.toml` at schema version 1
  and empty, bannered, source-digested Python and proof indexes.
- The generated quality gate classifies every repository path into exactly
  one of FOUNDATION, PRODUCT, DERIVED, or DECLARATION, rejecting a changed
  zone vocabulary, overlapping roots, ambiguous ownership, and unclassified
  paths.
- One capability validator enforces required structure, dependency direction,
  the domain import allowlist, and the `api.py` public surface for both system
  and product capability roots with the same rule identifiers.
- Pack tests reject any template file that would render into a PRODUCT root
  and use real Copier updates to prove that every customized seeded product
  byte remains unchanged while foundation and derived files change. A
  deliberate product-overwrite mutant proves the SHA-256 oracle is sensitive.
- The linked-worktree validation probe now lives under the declared
  `tests/unit` FOUNDATION root, so the new ownership guard checks the probe
  without weakening repository coverage.

The root and generated READMEs and the downstream agent contract describe the
four-zone contract and update boundary.

## Commands and actual results

Focused acceptance stories:

```bash
uv run --no-project --python 3.14 --with pytest==9.1.1 pytest -q \
  -o addopts='' \
  tests/unit/scripts/test_capability_validator.py \
  tests/unit/scripts/test_ownership_guard.py \
  tests/unit/generated/test_empty_repository_state.py
# 3 passed in 1.93s (fresh generated repository)

uv run --no-project --python 3.14 --with pytest==9.1.1 \
  --with copier==9.17.0 pytest -q \
  tests/test_ownership_zones.py tests/test_update_preservation.py
# 2 passed in 8.74s
```

Canonical completion gate:

```bash
just validate
```

The final `just validate` passed end to end:

- pack suite: **201 passed, 10 warnings in 73.50s**;
- template cleanliness and complete Jinja rendering: passed;
- generated Ruff and BasedPyright: passed with **0 type errors and
  0 warnings**;
- generated ownership, architecture, documentation, proof, symbolic, and
  import-contract gates: passed;
- generated tests: **174 passed, 7 skipped, 3 deselected**, with **93.94%**
  coverage;
- missing-hook repair, syntax fault injection, clean/dirty doctor probes, and
  linked-worktree pre-commit/pre-push execution: passed;
- Copier update round trip: **2 passed in 56.01s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- One immediately preceding `just validate` run reached linked pre-push after
  all deterministic checks passed, then the existing bounded CrossHair canary
  failed to refute on its third invocation. It had refuted on the first two
  invocations in that run, and all three refuted in the final passing run.
  Treat this as an existing symbolic-budget flake, not evidence that the
  deterministic ownership checks are unstable.
- Capability generation, lifecycle transitions, and derived-index
  recompilation remain later SPEC-0001 epics by design. This change establishes
  only the empty-N0 declarations, indexes, and structural contracts.
- Validation ran on Linux x86_64 only. macOS and Windows were not exercised.
- The root project intentionally has no development environment or lockfile;
  focused maintainer tests must continue to use `uv run --no-project`.
