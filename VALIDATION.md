# Validation record — 2026-07-28

Validated in the Orca Linux workspace (Linux 6.8.0-136-generic x86_64) with
Python 3.14.3, uv 0.11.28, just 1.56.0, Copier 9.17.0, pytest 9.1.1, and
pytest-xdist 3.8.0.

## Change validated

The generated-tree checksum assertion was removed from
`tests/test_instantiate.py`. The fast guard now proves a successful default
render through the existing expected-file and no-unrendered-Jinja checks,
retains pin-coherence and hook-policy coverage, and has a test that reads the
`test-fast` recipe to enforce that selection.

The four existing variant comparisons were not weakened: their names now share
the `delta_or_identical` selector, while their exact file-set and content
assertions remain unchanged. This makes the required focused command select the
coverage directly.

## Commands and actual results

```bash
just test-fast
```

Passed: **9 passed**. It generated the complete default repository, checked the
expected output files and Jinja rendering, and ran the recipe, pin-coherence,
and hook-policy tests.

```bash
uv run --no-project --python 3.14 --with pytest==9.1.1 --with copier==9.17.0 \
  pytest -q tests/test_instantiate.py -k delta_or_identical
```

Passed: **4 passed, 52 deselected**. The expected Copier dirty-template
warnings appeared because this focused run exercised the uncommitted test
rename before its checkpoint commit.

```bash
just validate
```

Passed end to end. The generator suite, fresh generated-repository validation,
and downstream quality gate all completed successfully; the final update
round-trip phase reported **2 passed in 41.36s**.

## Template-addition probe

In an isolated temporary clone, I added a new plain file under `template/` and
ran `just test-fast` without changing any test expectation. It passed with
**9 passed in 2.24s**. The probe file and temporary clone were removed before
the branch's final commit.

## Remaining risks and portability notes

- The root project deliberately has no development virtual environment, so the
  focused pytest command above uses `uv run` as required by the maintainer
  contract.
- The frozen `epics/` record quotes the retired checksum name as part of this
  leaf's acceptance prose. The coordinator ruled that text out of scope; the
  executable and documentary pack surface outside `epics/` is clean.
