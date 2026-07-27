# Validation record — 2026-07-27

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just 1.56.0,
Git 2.55.0, Copier 9.17.0, pytest 9.1.1, and pytest-xdist 3.8.0.

## Change validated

The template pack no longer has an optional architecture-diagram feature. The
generator, Copier answers, CLI, generated gate, CI, dependency setup, tests,
documentation, validation flow, and feature-specific template assets were
removed together. The generated repository has one materialization path.

## Commands and actual results

```bash
just validate
```

Final result: passed.

- Pack tests: 267 passed with 25 expected `DirtyLocalWarning` warnings in
  67.37s.
- Template cleanliness and complete Jinja rendering: passed.
- Generated bootstrap installed both prek hooks and passed the complete
  generated gate.
- Generated tests: 145 passed, 7 skipped, 3 session tests deselected; branch
  coverage 93.44%.
- The missing-hook repair, tracked syntax rejection, doctor clean/dirty,
  linked-worktree pre-commit, linked-worktree full pre-push, and cleanup probes
  passed.
- Previous-release and generated-recipe Copier update acceptance: 2 passed in
  32.74s.

## Tests updated

- `tests/test_instantiate.py`: removed feature-specific generation and drift
  checks while preserving the generated-tree contract.
- `tests/test_pin_coherence.py`: removed pins that no longer exist.
- `tests/test_benchmark_pipeline.py`: updated the expected Copier answers.

## Remaining risks and portability notes

- The canonical validation still resolves dependencies from the network when
  they are absent from the local cache.
