set shell := ["bash", "-euo", "pipefail", "-c"]

# Keep bytecode caches out of the source tree: every Python run through these
# recipes (and the pre-commit hooks, which call them) writes its __pycache__
# mirror under .venv instead.
export PYTHONPYCACHEPREFIX := justfile_directory() / ".venv/pycache"

langfuse_dir := justfile_directory() / "benchmarks/langfuse"
langfuse_compose := langfuse_dir / "compose.yaml"
langfuse_env := langfuse_dir / ".env"

default:
    @just --list

# Unit tests for the generator (instantiate.py). Fast; no downstream install, no Bun.
# Copier powers generation and grimp powers the diagram-sync subprocess tests.
# Keep Copier coherent with pyproject.toml and copier.yml; keep grimp coherent
# with template/pyproject.toml.jinja.
test:
    uv run --no-project --python 3.14 --with pytest==9.1.1 --with copier==9.17.0 --with grimp==3.15 pytest -q tests

# Canonical pack validation: generator tests, then a fresh instantiation in a
# temporary directory that must pass the generated repository's full quality gate.
validate: test
    uv run --no-project --python 3.14 --with copier==9.17.0 python scripts/validate_pack.py

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

# Create the ignored local Langfuse environment with fresh random secrets.
langfuse-init:
    python3 "{{langfuse_dir}}/init_env.py"

# Start the optional local Langfuse v3 lab and wait for its containers.
langfuse-up:
    test -f "{{langfuse_env}}" || { echo "missing {{langfuse_env}}; run 'just langfuse-init' first" >&2; exit 2; }
    docker compose --project-directory "{{langfuse_dir}}" --env-file "{{langfuse_env}}" -f "{{langfuse_compose}}" up --detach --wait

# Exit zero only when the local Langfuse public health API responds.
langfuse-status:
    curl --fail --silent --show-error --max-time 5 http://127.0.0.1:3000/api/public/health >/dev/null

# Stop and remove the local Langfuse containers (persistent volumes are kept).
langfuse-down:
    docker compose --project-directory "{{langfuse_dir}}" --env-file "{{langfuse_env}}" -f "{{langfuse_compose}}" down --remove-orphans

# List traces received by the local Langfuse API in the last N minutes.
langfuse-traces minutes="60":
    python3 "{{langfuse_dir}}/recent_traces.py" --minutes "{{minutes}}"

# Install and configure the pinned official Langfuse Claude Code plugin.
langfuse-hook-install:
    python3 "{{langfuse_dir}}/claude_hook.py" install

# Verify that the pinned Langfuse Claude Code plugin is enabled.
langfuse-hook-status:
    python3 "{{langfuse_dir}}/claude_hook.py" status

# Remove the Langfuse Claude Code plugin and its managed marketplace.
langfuse-hook-uninstall:
    python3 "{{langfuse_dir}}/claude_hook.py" uninstall
