set shell := ["bash", "-euo", "pipefail", "-c"]
set positional-arguments := true

# Keep bytecode caches out of the source tree: every Python run through these
# recipes writes its __pycache__ mirror under .venv instead.
export PYTHONPYCACHEPREFIX := justfile_directory() / ".venv/pycache"
# pack/ carries the `scripts` and `verification` packages of the tree.
export PYTHONPATH := justfile_directory() / "pack"
export SESSION_PROFILER_DEPENDENCY := "session-profiler-optimizer @ git+https://github.com/feltroidprime/session-profiler-optimizer.git@6ace879e8642777658576a47e0f53b32a1ddc0f7"

default:
    @just --list

bootstrap:
    uv sync --all-groups
    uv run prek install -f
    just check

check:
    uv run python pack/scripts/quality_gate.py --fix

# Fast local proof loop: structural closure, bounded generators, symbolic core.
prove:
    uv run python -m scripts.proof_guard
    HYPOTHESIS_PROFILE=fast uv run pytest -q -m proof pack/verification -o addopts="--strict-config --strict-markers --disable-socket"
    uv run python -m scripts.crosshair_gate fast

# Sub-second-to-seconds feedback on one changed law; the structural catalog still closes globally.
prove-one property_id:
    uv run python -m scripts.proof_guard
    HYPOTHESIS_PROFILE=fast uv run pytest -q -m proof pack/verification --property-id "$1" -o addopts="--strict-config --strict-markers --disable-socket"
    uv run python -m scripts.crosshair_gate fast "$1"

# Larger search budget for release candidates, risky concurrency changes, or nightly CI.
prove-deep:
    uv run python -m scripts.proof_guard
    HYPOTHESIS_PROFILE=deep uv run pytest -q -m proof pack/verification -o addopts="--strict-config --strict-markers --disable-socket"
    uv run python -m scripts.crosshair_gate deep

proof-report:
    uv run python -m scripts.proof_guard --report

doctor:
    uv run --no-sync python -m scripts.doctor

# Preserve one complete Claude Code or Codex CLI session as local ATIF evidence.
session-log input output=".agent-sessions" agent="auto":
    uv run --with "$SESSION_PROFILER_DEPENDENCY" session-profiler --agent "$3" "$1" "$2"

# Opt-in: reads private local logs and samples one session from each size quintile.
session-e2e:
    uv run --with "$SESSION_PROFILER_DEPENDENCY" pytest -q -m session_e2e -o addopts="--strict-config --strict-markers --disable-socket" pack/tests/e2e

update:
    uv lock --upgrade
    uv run prek update
    just check

# Create an annotated PEP 440 release tag after verifying its changelog entry
# and a clean working tree. Tags are pushed separately by the release operator.
release version:
    python3 pack/scripts/release.py "{{version}}"

# Install a durable prek executable plus this repository's pre-commit and
# pre-push hooks. Safe to re-run; rewiring the same managed hooks is idempotent.
hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v prek >/dev/null 2>&1; then
        uv tool install "prek>=0.4.9"
    fi
    prek install -f
