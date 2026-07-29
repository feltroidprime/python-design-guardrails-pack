# Validation record — 2026-07-29

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.3,
uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11. The final canonical run exercised the
committed issue #43 tree; the only subsequent change was this validation
record.

## Change validated

The SPEC-0001 repository-generation planning epic (#36, with DAG leaves
#37–#43) is complete:

- Generated repositories contain a real
  `repoctl.modules.repository_generation` hexagonal capsule rather than a
  placeholder.
- Immutable intent, snapshot, operation, and plan values have canonical JSON,
  content-derived identities, exact preconditions, and explicit ownership
  roots.
- The proof catalog discovers product and repository-control roots through one
  policy. Exact derived-index compilation, closed path classification, and
  deterministic planning carry `REPOCTL::DERIVED-INDEX-EXACT`,
  `REPOCTL::PLAN-PATH-CLOSED`, and `REPOCTL::PLAN-DETERMINISTIC`.
- Planning is pure and deterministic over 0–100 capability snapshots. It
  creates only absent PRODUCT seeds and emits exact declaration/derived writes;
  effectful application remains deliberately outside this epic.
- The actual capability validator runs identical `CAP001`–`CAP003` rule sets
  against a FOUNDATION repoctl capability and a PRODUCT fixture. Mutation and
  AST/config audits reject a system-only skipped rule or bypass.
- Root and generated Python now use the same Ruff floor and policy. The root
  pre-push hook runs all root tests with four work-stealing workers, while the
  slower generated, symbolic, hook-repair, worktree, and offline-update matrix
  remains canonical in `just validate` and CI.

## Commands and actual results

Focused parity and policy checks:

```bash
uv run --no-project --python 3.14 --with pytest==9.1.1 \
  --with copier==9.17.0 --with "icontract>=2.7.3" pytest -q \
  tests/test_selfhost_validator.py
# 3 passed

just prove-one REPOCTL::PLAN-DETERMINISTIC
# 2 passed, 30 deselected; bounded CrossHair target and canary passed

just prove
# 24 passed, 8 deselected; six real CrossHair targets and canary passed
```

Pre-push performance diagnosis and acceptance:

```bash
uv run --no-project --python 3.14 --with pytest==9.1.1 \
  --with pytest-xdist==3.8.0 --with copier==9.17.0 \
  --with "icontract>=2.7.3" pytest -q -n auto --dist loadscope \
  --durations=30 tests
# 214 passed in 63.77s; the module-scoped scheduler serialized Copier-heavy tests

hyperfine --runs 1 \
  "uv run --no-project --python 3.14 --with pytest==9.1.1 \
  --with pytest-xdist==3.8.0 --with copier==9.17.0 \
  --with 'icontract>=2.7.3' pytest -q -n 8 --dist worksteal tests"
# 214 passed; 38.828s

# Actual installed pre-push shim, final four-worker policy:
# pack push checks (full root suite, <60s) ... Passed
# 41.079s wall time
```

Canonical completion gate:

```bash
just validate
```

The final `just validate` passed end to end:

- root Ruff repair/check: **120 files stable**, all checks passed;
- root suite: **214 passed in 29.72s** with four work-stealing workers;
- template cleanliness and complete Jinja rendering: passed;
- generated Ruff and BasedPyright: passed with **0 type errors and
  0 warnings**;
- generated ownership, architecture, documentation, proof, symbolic, and
  import-contract gates: passed;
- generated tests: **201 passed, 7 skipped, 3 deselected in 27.77s**, with
  **93.94%** coverage;
- deterministic repair replay: **201 passed, 7 skipped, 3 deselected in
  24.36s**, with the same coverage;
- missing-hook repair, tracked-syntax fault injection, clean/dirty doctor
  probes, and linked-worktree pre-commit/pre-push execution: passed;
- committed Copier update round trip and offline downstream gate:
  **2 passed in 69.82s**.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

Earlier runs honestly exposed and drove three fixes before the final pass:

- the CI symbolic canary needed a profile-independent minimum search budget;
- root-default Ruff repair differed from the generated policy and left repair
  drift;
- a package-dependent Jinja import order (and then one excess blank line)
  failed the committed update round trip and repair-byte comparison.

## Remaining risks and portability notes

- CrossHair results are bounded searches, not exhaustive proofs.
- The epic plans repository changes but intentionally does not apply them or
  implement capability lifecycle transitions; those remain later SPEC-0001
  work.
- Full `just validate` remains a deliberately comprehensive, multi-minute
  completion/CI gate. Only interactive pre-push validation is budgeted below
  one minute.
- Validation and profiling ran on Linux x86_64 only. macOS and Windows were
  not exercised.
- The root remains lock-free. Its Ruff floor is coherence-tested against the
  generated dependency floor, but a future resolver may select a newer tool
  version than the one recorded here.
