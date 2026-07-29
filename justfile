set shell := ["bash", "-euo", "pipefail", "-c"]

# Keep bytecode caches out of the source tree: every Python run through these
# recipes (and the prek hooks, which call them) writes its __pycache__
# mirror under .venv instead.
export PYTHONPYCACHEPREFIX := justfile_directory() / ".venv/pycache"

default:
    @just --list

# Unit tests for the generator (instantiate.py). Fast; no downstream install.
# Keep Copier coherent with pyproject.toml and copier.yml.
test:
    uv run --no-project --python 3.14 --with pytest==9.1.1 --with pytest-xdist==3.8.0 --with copier==9.17.0 --with "icontract>=2.7.3" pytest -q -n auto --dist loadscope tests

# Fast pre-commit guard: render the complete default template, keep pins
# coherent, and verify that pre-push still owns the comprehensive validation.
test-fast:
    uv run --no-project --python 3.14 --with pytest==9.1.1 --with copier==9.17.0 --with "icontract>=2.7.3" pytest -q tests/test_instantiate.py::test_expected_files_are_preserved tests/test_instantiate.py::test_no_unrendered_jinja_survives tests/test_instantiate.py::test_fast_recipe_renders_default_template_and_runs_policy_checks tests/test_pin_coherence.py tests/test_hook_policy.py

# Canonical pack validation: generator tests, then a fresh instantiation in a
# temporary directory that must pass the generated repository's full quality gate.
validate: test
    uv run --no-project --python 3.14 --with copier==9.17.0 python scripts/validate_pack.py
    PACK_RUN_DOWNSTREAM_GATE=1 uv run --no-project --python 3.14 --with pytest==9.1.1 --with pytest-xdist==3.8.0 --with copier==9.17.0 --with "icontract>=2.7.3" pytest -q -n 2 tests/test_update_roundtrip.py

# Create an annotated PEP 440 template tag after verifying its changelog entry
# and a clean working tree. Tags are pushed separately by the release operator.
release version:
    python3 scripts/release.py "{{version}}"

# Install the `python-repo` CLI system-wide with uv (editable: template edits
# and `git pull` take effect without reinstalling).
install:
    uv tool install --force --editable .

# Install a durable prek executable plus this repo's pre-commit and pre-push
# hooks. Safe to re-run; rewiring the same managed hooks is idempotent.
hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v prek >/dev/null 2>&1; then
        uv tool install "prek>=0.4.9"
    fi
    prek install -f
