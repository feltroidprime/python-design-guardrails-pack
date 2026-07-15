# Agent session observability

This is the owner of the repository's optional Langfuse workflow. It captures
complete Codex and Claude Code turns so a human can inspect the work in
Langfuse and an agent can analyze the same session as a local JSON transcript.

## Privacy boundary

Tracing is off until a contributor runs the install command with valid project
credentials. Once enabled, the official plugins can upload full prompts,
assistant messages and reasoning summaries, tool inputs and outputs, source
fragments, command output, injected skill instructions, model metadata, token
usage, and subagent activity.
That content may contain secrets or proprietary code. Use a Langfuse project
with the right access and retention policy; do not enable tracing for data that
must not leave the workstation or the approved self-hosted instance.

Both upstream plugins normally cap each captured field at 20,000 characters.
The installer deliberately raises that cap to 2,147,483,647 so the recorded
session is not locally truncated. Set `AGENT_OBSERVABILITY_MAX_CHARS` during
installation only when you intentionally want a smaller ceiling. Full capture
can create very large traces, and a hosted or self-hosted Langfuse deployment
may still impose its own request or storage limit.

Credentials live only in ignored, mode-`0600` local files named
.codex/langfuse.json and .claude/settings.local.json. The tracked example shape
is [`.codex/langfuse.example.json`](../.codex/langfuse.example.json). Never
commit, print, or paste the real files into an agent prompt.

## Enable tracing

Create or select a Langfuse project and expose its project-scoped keys only for
the install process:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-... \
LANGFUSE_SECRET_KEY=sk-lf-... \
LANGFUSE_BASE_URL=https://cloud.langfuse.com \
just agent-observability-install
```

The default command requires both supported agents. Set
`AGENT_OBSERVABILITY_AGENT=codex` or `AGENT_OBSERVABILITY_AGENT=claude` before
the command when the repository intentionally uses only one. The installer
pins the official Langfuse sources to reviewed Git revisions, stores no
credential in tracked files, and fails before mutation when credentials are
missing. Later single-agent installs must keep the same Langfuse base URL and
public project key; rotating the secret updates every already-managed agent so
the shared corpus cannot split. The installer refuses to take over an
unmanaged local Claude Langfuse plugin or settings. It can reuse a globally
listed Langfuse marketplace only when its Git checkout is clean and exactly at
the reviewed commit; the project records that it does not own that marketplace
and never removes it. Status also compares every installed Claude cache file
with the reviewed checkout, while the Codex hook rechecks its clean commit
immediately before execution. Codex tracing requires Node.js 22 or newer and
uses an ignored project-local hook, so it never replaces a user-global plugin.
Restart the agents; in Codex, open `/hooks` and trust the reviewed project hook
when prompted. Then verify the local setup without revealing keys:

```bash
just agent-observability-status
```

Installation is the project opt-in. The upstream Codex plugin also accepts the
process-level `TRACE_TO_LANGFUSE=true` switch; because environment variables
take precedence, remove that variable when testing the project-level disable.

## Turn a session into feedback

After doing real work normally, build a recent cross-session corpus and count
diagnostic codes that recur at least twice:

```bash
AGENT_OBSERVABILITY_LOOKBACK_MINUTES=1440 just agent-observability-analyze
```

The private JSON result contains every retained repository trace and
observation plus a summary grouped by diagnostic code, occurrence count, trace
count, session count, and representative messages. Use
`AGENT_OBSERVABILITY_MINIMUM_SESSIONS` to change the distinct-session
recurrence threshold. Traces are retained only when their recorded repository
root or working directory belongs to this repository. This makes patterns such
as `E501` visible across sessions while leaving the underlying corpus available
for deeper agent analysis.

List recent traced turns when you need a specific session identifier:

```bash
AGENT_OBSERVABILITY_LOOKBACK_MINUTES=120 just agent-observability-recent
```

Copy the session identifier, then export every trace and nested observation in
that session:

```bash
LANGFUSE_SESSION_ID=SESSION_ID just agent-observability-export
```

The command writes an ignored, mode-`0600` file below the local
agent-observability transcript directory. An agent can read that file and trace
a failure backward through prompts, repeated reads, tool calls, command output,
retries, and the final response. Keep the causal chain explicit:

1. Name the repeated symptom and count where it occurs.
2. Locate the first decision or missing context that made it likely.
3. Classify the owner: task prompt, agent contract, `just` workflow, automatic
   fixer, quality gate, architecture rule, or template example.
4. Propose the smallest template or harness hypothesis that would prevent the
   recurrence, then add a regression test or benchmark variant before adopting
   it.
5. Compare later sessions by agent, model, repository, template revision, time,
   tool calls, and quality outcome. A single anecdote starts a hypothesis; it
   does not prove a broad guardrail change.

For example, repeated `E501 Line too long (109 > 100)` before `just fix` points
to workflow timing; the same error after `just fix` may be a comment or string
that Ruff deliberately cannot rewrite. The transcript distinguishes those two
causes and prevents weakening the line-length guardrail on guesswork.

Langfuse groups the per-turn traces under one session. Its UI is the convenient
human replay; the exported JSON is the stable handoff to another agent and can
be retained as evidence for a benchmark hypothesis.

## Disable and troubleshoot

```bash
just agent-observability-disable
```

Disabling requires Claude Code to remain available while a Claude plugin is
project-managed. If the CLI is missing, or if its uninstall command fails, the
operator still removes local credentials and hook opt-ins, but keeps the
ownership record and reviewed checkout intact; restore the CLI or fix the
reported error, then run the command again to finish external cleanup.

This scrubs the project credentials, removes the project-local Codex hook and
checkout, uninstalls the project-local Claude Code plugin, and writes an
explicit Codex opt-out when Codex was selected. Other project hook groups and
unrelated local settings are preserved. Installation records ownership before
external plugin mutation, so this command can also clean up a partially failed
setup. A process-level Langfuse enable flag or a separately installed user
plugin remains outside this repository's control.

If no trace appears, run `just agent-observability-status`, restart the agent,
and confirm that its process can reach the configured Langfuse base URL. The
hooks fail open so an observability outage never blocks coding work. Use the
Langfuse session list for human inspection and
`just agent-observability-export` when another agent needs the full transcript.

Upstream references: [Langfuse Codex tracing](https://langfuse.com/integrations/developer-tools/codex)
and [Langfuse Claude Code tracing](https://langfuse.com/integrations/developer-tools/claude-code).
