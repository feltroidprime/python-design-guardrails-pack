set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Unit tests for the generator (instantiate.py). Fast; no downstream install.
test:
    uv run --no-project --python 3.14 --with pytest==9.1.1 pytest -q tests

# Canonical pack validation: generator tests, then a fresh instantiation in a
# temporary directory that must pass the generated repository's full quality gate.
validate: test
    python3 scripts/validate_pack.py
