# Validation record — 2026-07-30

Validated on Linux 6.8.0-136-generic (x86_64) with Python 3.14.6,
uv 0.12.0, just 1.56.0, Copier 9.17.0, pytest 9.1.1, pytest-xdist
3.8.0, Ruff 0.16.0, and prek 0.4.11.

## Change validated

Issue #55 makes declaration-derived indexes a small, deterministic compiler
output.

- The compiler derives the active-capability, composition, product-CLI, and
  proof indexes only from explicit capability declarations—never runtime module
  discovery or product-source inspection.
- The declaration source hash is calculated from canonical declaration
  documents, preserving the empty repository's established baseline without
  scanning static product sources. Canonical declaration order makes repeated
  output byte-identical.
- A direct compiler-to-repository loop writes only changed files and checks that
  each target is classified as `DERIVED` immediately before writing it.
- Both adapters share a schema-validating declaration decoder backed by the
  domain's canonical lifecycle type and predicate, so unsupported schema
  versions fail before any derived output is written. Rendered Python
  references must belong to the declaration's product module or to the exact
  configured capability-name/system-module pair, and use Python's canonical
  hard-keyword predicate.
- Integration and unit tests cover empty output, active-versus-retired
  exactness, deterministic full-tree bytes, product and system proof ownership,
  forbidden discovery imports, DERIVED-only writes, hard-versus-soft keyword
  handling, and invalid declarations before a write occurs.

This intentionally does not add a recovery journal, cross-process lease, or
generic mutation protocol. Those mechanisms were beyond #55's declaration to
deterministic-output scope.

## Commands and actual results

```bash
PYTHONDONTWRITEBYTECODE=1 just validate
```

The final canonical `just validate` passed end to end (directly observed exit
code 0):

- root Ruff repair/check was stable across 143 files and the root test suite
  passed with **213 passed, 11 warnings** in 23.59s;
- template cleanliness, fresh instantiation, generated bootstrap, downstream
  repair probes, missing-hook repair, tracked-syntax and dirty-doctor fault
  probes, and linked-worktree pre-commit/pre-push checks all passed;
- the generated type gate reported **0 errors, 0 warnings**; ownership,
  architecture, documentation, proof-contract, symbolic-core, and import
  contracts all passed;
- the generated full quality run passed with **265 passed, 8 skipped, 3
  deselected** in 60.42s and **93.94%** coverage (90% required). The hook-repair
  rerun also passed with **265 passed, 8 skipped, 3 deselected** in 58.82s.

The syntax and dirty-doctor failures printed during validation are deliberate
fault-injection probes.

## Remaining risks and portability notes

- Full validation ran on Linux x86_64 only. macOS and Windows remain
  unexercised; their subprocess environment and filesystem behavior can differ.
- A run replaces multiple derived files through independent conditional writes,
  so an abrupt process termination can leave a mixed generation. The next
  regeneration deterministically rewrites the current declaration output; #55
  deliberately does not provide crash recovery or cross-process coordination.
- Lifecycle validation and execution of rendered product imports are delivered
  by later epic leaves.
