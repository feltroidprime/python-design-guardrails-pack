# Validation record — 2026-07-17

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just
1.56.0, Bun 1.3.9, Git 2.55.0, Copier 9.17.0, pytest 9.1.1, and
pytest-xdist 3.8.0. Copier emitted 25 expected `DirtyLocalWarning` instances
because the canonical template changes were intentionally uncommitted.

## Change validated

GR-19 harvests five recurring review findings into the generated repository's
shared architecture AST guard:

1. ARCH026 rejects module-scope mutable list/dict/set state, including state
   inside module control flow, while allowing list-valued `__all__`.
2. ARCH027 rejects exact same-named, same-definition Enum copies across
   in-repository modules.
3. ARCH028 detects untokenized `str` parameters and fields used as path
   operands without duplicating ARCH019/020.
4. ARCH029 rejects used CamelCase domain aliases to bare primitives, including
   legacy `TypeAlias` declarations.
5. ARCH030 requires `@override` for methods resolved against direct
   in-repository bases and explicit Protocol bases.

ADR-0006 records the conservative heuristic boundaries. Each code has
violating and clean fixtures plus shared ADR-marker suppression coverage.

## Commands and actual results

### Generated repository gate

```bash
just check
```

Run in a freshly generated and bootstrapped default repository. Ruff,
BasedPyright (0 errors, 0 warnings), architecture, documentation, both import
contracts, diagram sync, LikeC4 validation, and tests passed. Tests: 145
passed, 7 skipped, 3 session tests deselected; branch coverage was 93.44%.

### Canonical pack validation

```bash
just validate
```

Final result: passed.

- Pack tests: 263 passed with 25 expected warnings in 51.30s.
- Template cleanliness and complete Jinja rendering: passed.
- Generated bootstrap resolved 23 packages, installed 22, installed both prek
  hooks, and passed the complete generated gate.
- The missing-hook repair, tracked syntax rejection, doctor clean/dirty,
  linked-worktree pre-commit, linked-worktree full pre-push, and cleanup probes
  passed.
- Previous-release and generated-recipe Copier update acceptance: 2 passed in
  22.97s.

### Focused evidence

The five checks were planted together in a temporary generated repository;
the guard reported exactly ARCH026, ARCH027, ARCH028, ARCH029, and ARCH030,
then passed after the scratch files were removed. The permanent focused suite
and largest benchmark scenario also passed without changing the 400,000
character bundle ceiling.

## Tests added or updated

- `tests/test_review_discipline.py` supplies positive and negative fixtures for
  ARCH026–ARCH030, supported path-call cases, ARCH019 de-duplication, external
  base ambiguity, conditional module state, legacy `TypeAlias`, and shared
  ADR-marker suppression.
- Existing None, Path, and CLI discipline tests now use the repository-wide
  guard seam.
- Generated-file inventory and deterministic tree digest include ADR-0006 and
  the two new rule modules.
- Existing generated fixtures were converted from mutable module dictionaries
  and sets to local factories, tuples, and frozensets.

## Remaining risks and portability notes

- ARCH027 intentionally covers exact same-named Enum definitions only; broader
  dataclass, validator, fixture, and semantic-model duplication remains review
  work because deterministic equivalence would be noisy.
- ARCH028 is lexical and recognizes the documented direct path APIs; aliases
  and interprocedural flows may be missed.
- ARCH029 follows same-module boundary use only. `JsonString` and `JsonNumber`
  are the documented wire-scalar allowlist.
- ARCH030 resolves same-module and direct absolute imports. Relative imports,
  module-import aliases, transitive ancestors, structural Protocol matches,
  re-exports, dynamic bases, and ambiguous names deliberately under-flag.
- Full validation retains the documented Python 3.14, uv, just, Bun, Git, and
  first-resolution network prerequisites.
