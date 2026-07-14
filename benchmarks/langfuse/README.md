# Local Langfuse operations

This optional lab runs Langfuse OSS v3 and its PostgreSQL, ClickHouse, Redis,
and MinIO dependencies on Docker. It is deliberately separate from the
benchmark harness and from `just test`/`just validate`; deterministic tests
only inspect its configuration and exercise its scripts against fakes.

The Compose project is `guardrails-langfuse`. All published ports bind to
`127.0.0.1`; the Langfuse UI and API are at <http://127.0.0.1:3000> and the
MinIO API/console are at ports 9090/9091. Every image has an exact version tag
in `compose.yaml`.

## Set up and operate the stack

Prerequisites are Docker with Compose, `curl`, and Python 3.10 or newer. The
Claude hook additionally needs `git`, Claude Code's `claude` CLI, and `uv` on
`PATH` (or Python with `langfuse>=4,<5`).

```bash
just langfuse-init       # create ignored .env with random local secrets, mode 0600
just langfuse-up         # start the six containers and wait for health
just langfuse-status     # exits 0 only when /api/public/health responds
```

`langfuse-init` refuses to overwrite an existing `.env`. The committed
`.env.example` documents every setting but intentionally contains no secret
value. The generated `.env` contains the first-start user, project API keys,
and infrastructure credentials; it is gitignored and must not be shared.
Langfuse applies the `LANGFUSE_INIT_*` values only when initializing empty
volumes, so keep the `.env` with those volumes.

Stop and remove all lab containers and its network while retaining data:

```bash
just langfuse-down
docker compose --project-directory benchmarks/langfuse \
  --env-file benchmarks/langfuse/.env \
  -f benchmarks/langfuse/compose.yaml ps    # empty after down
```

To discard all local Langfuse data, run `just langfuse-down`, then repeat the
Compose command above with `down --volumes`. Delete the ignored `.env` only
after removing the volumes; a new environment file creates different keys.

## Install the Claude Code tracing hook

The selected integration is Langfuse's maintained
[`Claude-Observability-Plugin`](https://github.com/langfuse/Claude-Observability-Plugin),
version 1.0.0 pinned to commit
`3f301f3840c975bdbd16b8140140d139f27aa99b`. It was preferred to the
third-party `claude-code-langfuse-hook` package because Langfuse maintains it,
it uses Claude Code's plugin configuration/keychain path, covers both `Stop`
and `SessionEnd`, pins the supported Langfuse SDK range, and fails open. The
installer clones and verifies that exact commit rather than following a
floating marketplace branch.

With the stack healthy:

```bash
just langfuse-hook-install
just langfuse-hook-status
```

The installer reads the ignored `.env`, registers a user-scope marketplace,
and configures the plugin for `http://127.0.0.1:3000`; it never prints the API
keys. Restart Claude Code so new sessions load the hook. Then run a normal
interactive session, submit at least one turn, exit it, and verify ingestion
without opening the UI:

```bash
claude
just langfuse-traces 15
```

`just langfuse-traces` uses Basic authentication from `.env` and lists trace
timestamps, names, and IDs from `/api/public/traces`. The secret key is never
printed. Traces contain prompts, responses, tool inputs/outputs, paths, and
token usage; treat the local volumes as sensitive data.

Disable and fully remove the installed plugin, its user-scope marketplace,
configuration, and managed checkout with:

```bash
just langfuse-hook-uninstall
```

Re-run `just langfuse-hook-install` to restore it. Stack lifecycle and hook
lifecycle are independent.

## Benchmark neutrality

The user-scope plugin also observes headless Claude Code sessions. It is not
inert during real Claude benchmark runs, but it is symmetric between arms:
both builders inherit the same host Claude settings and use the same hook.
The hook is fail-open when the stack is down. It can still add a bounded local
connection/flush attempt to absolute timings, so keep its enabled/disabled
state fixed across a campaign; disable it with `just langfuse-hook-uninstall`
when measuring an environment without tracing.

Fake-agent benchmark tests never launch Claude Code, import this lab, or make
a Langfuse request. Consequently the stack can remain down for `just test` and
the deterministic fake-agent pipeline.

## Export completed benchmark runs

The harness's provider-neutral exporter is separate from the Claude hook. Set
`[langfuse].enabled = true` in the selected benchmark config, export the local
project keys, and run the benchmark normally:

```bash
set -a
source benchmarks/langfuse/.env
set +a
just benchmark benchmarks/config/smoke.toml
```

Export runs after result/report generation and fails open with a warning. It
creates one trace per arm with pipeline spans, identity tags, and numeric
scores, regardless of the builder provider. The full config and saved
dashboard recipe are in the [benchmark guide](../README.md).

The opt-in fake-agent round trip is outside the deterministic suite:

```bash
LANGFUSE_INTEGRATION=1 uv run --no-project --python 3.14 \
  --with pytest==9.1.1 --with copier==9.17.0 \
  pytest -q benchmarks/integration/test_langfuse_export.py
```

## OpenTelemetry fallback

If the plugin becomes incompatible with Claude Code, Langfuse v3 also accepts
OTLP/HTTP. An existing Claude/OpenTelemetry exporter can target:

```text
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:3000/api/public/otel
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:3000/api/public/otel/v1/traces
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64(public-key:secret-key)>,x-langfuse-ingestion-version=4
```

Use the `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` from the ignored
`.env`; do not write the encoded credential into a tracked file. Langfuse
supports OTLP over HTTP/JSON or HTTP/protobuf, not OTLP/gRPC. The native
plugin remains the default because it reconstructs Claude turns, generations,
tools, and sessions rather than exporting only generic spans.

## Troubleshooting

- `langfuse-up` cannot reach Docker: start Docker Desktop (macOS/Windows) or
  the Docker daemon, then confirm `docker info` succeeds.
- A container is unhealthy: run `docker compose --project-directory
  benchmarks/langfuse --env-file benchmarks/langfuse/.env -f
  benchmarks/langfuse/compose.yaml ps` and the same prefix followed by
  `logs --tail=200 <service>`.
- Health works but API authentication fails: the volumes and `.env` may come
  from different initializations. Preserve the matching file or reset both as
  described above.
- No Claude trace: confirm `just langfuse-hook-status`, restart Claude Code,
  run a genuine top-level interactive session, and retry `just
  langfuse-traces 15` after a few seconds.
- Hook diagnosis: launch a session as `CC_LANGFUSE_DEBUG=true claude`, then
  inspect `~/.claude/state/langfuse_hook.log`. The hook exits successfully on
  missing dependencies, credentials, transcripts, or an unavailable API so it
  cannot block Claude Code.

Upstream references: [Claude Code integration](https://langfuse.com/integrations/developer-tools/claude-code),
[public API authentication](https://langfuse.com/docs/api-and-data-platform/features/public-api),
and [OTLP ingestion](https://langfuse.com/integrations/native/opentelemetry).
