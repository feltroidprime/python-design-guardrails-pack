set shell := ["bash", "-euo", "pipefail", "-c"]

# Keep bytecode caches out of the source tree: every Python run through these
# recipes (and the pre-commit hooks, which call them) writes its __pycache__
# mirror under .venv instead.
export PYTHONPYCACHEPREFIX := justfile_directory() / ".venv/pycache"

default:
    @just --list

# Unit tests for the generator (instantiate.py). Fast; no downstream install, no Bun.
# grimp powers the diagram-sync subprocess tests; keep the pin equal to the
# template's dev-group pin (template/pyproject.toml).
test:
    uv run --no-project --python 3.14 --with pytest==9.1.1 --with grimp==3.15 pytest -q tests

# Canonical pack validation: generator tests, then a fresh instantiation in a
# temporary directory that must pass the generated repository's full quality gate.
validate: test
    python3 scripts/validate_pack.py

# Install the `python-repo` CLI system-wide with uv (editable: template edits
# and `git pull` take effect without reinstalling).
install:
    uv tool install --force --editable .

# End-to-end value benchmark: one LLM builds the same app with and without the
# template; objective metrics + a blind LLM judge panel compare the results.
# Long and costs provider usage — see benchmarks/README.md before running.
# Pick the app (config file) and the coding model without editing TOML:
#   just benchmark                                          # ledger app, config model
#   just benchmark benchmarks/config/smoke.toml             # tiny app
#   just benchmark benchmarks/config/default.toml haiku     # model alias or full id
#   just benchmark benchmarks/config/default.toml gpt-5.6-sol codex xhigh
benchmark config="benchmarks/config/default.toml" model="" provider="" effort="":
    python3 benchmarks/run.py --config {{config}} \
        {{ if model == "" { "" } else { "--builder-model " + model } }} \
        {{ if provider == "" { "" } else { "--builder-provider " + provider } }} \
        {{ if effort == "" { "" } else { "--builder-effort " + effort } }}
