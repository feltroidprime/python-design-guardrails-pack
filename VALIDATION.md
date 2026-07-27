# Validation record — 2026-07-27

Validated on macOS Apple Silicon with Python 3.14.6, uv 0.11.28, just 1.56.0,
Git 2.55.0, Copier 9.17.0, pytest 9.1.1, and pytest-xdist 3.8.0.

## Change validated

The meta-repository's pre-commit hook now runs a focused check that renders the
default template, verifies version-pin coherence, and protects the hook
routing. The complete pack suite and fresh generated-repository validation
remain at pre-push through `just validate`.

## Commands and actual results

```bash
just validate
```

Final result: passed.

- Pack tests: 268 passed with 25 expected `DirtyLocalWarning` warnings in
  65.55s.
- Template cleanliness and complete Jinja rendering: passed.
- Generated bootstrap installed both prek hooks and passed the complete
  generated gate.
- Generated tests: 145 passed, 7 skipped, 3 session tests deselected; branch
  coverage 93.44%.
- The missing-hook repair, tracked syntax rejection, doctor clean/dirty,
  linked-worktree pre-commit, linked-worktree full pre-push, and cleanup probes
  passed.
- Previous-release and generated-recipe Copier update acceptance: 2 passed in
  31.53s.

Focused hook measurements, with a warm dependency cache:

- `just test-fast`: 7 passed in 3.38s (4.27s wall-clock).
- Installed `.git/hooks/pre-commit`: passed in 4.57s wall-clock.

## Tests updated

- `tests/test_hook_policy.py`: added the contract that pre-commit runs the
  focused recipe and pre-push retains `just validate`.

## Remaining risks and portability notes

- The canonical validation still resolves dependencies from the network when
  they are absent from the local cache.
- The focused pre-commit guard deliberately does not replace the complete pack
  test suite; pre-push and CI remain the comprehensive enforcement points.
