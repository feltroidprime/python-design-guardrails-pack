# ADR-0003: Agent-session evidence comes from a pinned private library

- Status: accepted
- Date: 2026-07-16
- Owners: repository maintainers
- Revisit trigger: the private package becomes unavailable, Harbor exposes a
  stable public converter, or the evidence schema changes incompatibly

## Context and forces

Improving this repository's agent harness requires complete, comparable
evidence from Claude Code CLI and Codex CLI sessions. Native logs differ, can
be large, and contain sensitive prompts, source, and tool output. Conversion
must preserve raw evidence, detect loss, remain deterministic, and avoid
semantic inference.

Every project that the pack starts shares this capability. Copying its
implementation here would create one fork per project, and it would make a fix
to a native format impossible to release at one time.

## Decision

Use the private `session-profiler-optimizer` Python package as the sole
implementation. The opt-in `session-log` and `session-e2e` recipes inject it
with `uv run --with` from Git over HTTPS at immutable commit
`6ace879e8642777658576a47e0f53b32a1ddc0f7`. It is deliberately absent from the
project dependency groups and lockfile, so the first setup, the quality checks
and CI stay usable without credentials for a second repository. Before an opt-in
session command, GitHub CLI configures the normal Git credential helper with
`gh auth setup-git`; credentials are not recorded in this repository.

The package owns Harbor 0.18.0 and its compatible LiteLLM pin transitively. It
isolates Harbor's private `ClaudeCode` and `Codex` conversion methods, owns
native-format supplements, tests, the `session-profiler` console script, and
the stable API:

```python
convert_session(input_path, output_dir, agent_type="auto")
```

`scripts.agent_sessions` is deliberately only a lazy compatibility facade. The
`just session-log <input> [output] [agent]` recipe invokes the installed console
script directly and defaults to the dedicated ignored `.agent-sessions`
directory. No converter logic or Harbor API is duplicated in the generated
repository.

Auto-detection accepts complete Codex rollouts and Claude primary transcripts.
Codex `~/.codex/history.jsonl` is rejected because it is only a prompt index.
Claude subagent transcripts are discovered recursively; workflow journals are
retained as raw sidecars instead of being misrepresented as dialogue.

Each successful conversion writes exactly:

```text
output/
├── trajectory.atif.json
├── profile.tsv
├── route.txt
├── blobs/
└── manifest.json
```

The package snapshots native inputs once, preserves them byte-for-byte in
content-addressed blobs, validates ATIF-v1.7, and verifies raw/ATIF tool and
observation identities. The manifest also checks metrics, profile rows,
subagent links, hashes, and blob reachability. Conversion is transactional and
owner-only on POSIX.

Profile timing uses real call/result endpoints when available; otherwise it
records only a gap to the next event. Status uses explicit error, result,
status, and exit-code fields, never prompt or argument text. Fingerprints use
canonical type, operation, and arguments. Large step content moves to SHA-256
blobs while full ATIF remains intact.

`just session-e2e` is opt-in because it reads private files from the current
user's home directory. The consumer test randomly selects one primary Claude
and Codex transcript from each of five byte-size quantiles and validates every
manifest check. Routine `just check` excludes this marker.

## Alternatives considered

- **Copy the converter into every project.** Rejected: fixes and dependency
  pins would then drift apart.
- **Parse both formats locally without Harbor.** Rejected: it duplicates an
  active normalizer and broadens native-format maintenance.
- **Store ATIF only.** Rejected: normalized output cannot prove that an unknown
  native event was preserved.
- **Summarize with an LLM during conversion.** Rejected: semantic inference is
  nondeterministic and unsuitable for an evidence compiler.

## Consequences

### Positive

- Every project shares one reviewed implementation commit.
- Each project keeps a small stable facade and one simple command.
- Raw evidence and identity checks make silent call/result loss visible.

### Negative / cost accepted

- Session-evidence commands require authenticated read access to a private
  GitHub repository.
- Harbor and LiteLLM add a substantial transient dependency environment when
  an opt-in command runs.
- Updating the profiler requires a reviewed commit-pin change in the pack.

### Risks and mitigations

- **Private dependency auth:** run `gh auth login` and `gh auth setup-git` before
  an opt-in session command. The first setup and CI never request the package.
- **Native-format drift:** the package fails closed and replays fixtures plus
  random real-session quintiles before a new commit is pinned.
- **Credential leakage in evidence:** output is ignored by Git and private on
  POSIX; sharing remains a deliberate human decision.

## Validation

The package repository owns deterministic fixtures, safety regressions, more
than 90% branch coverage, and real-session E2E sampling. This repository keeps
an opt-in consumer test that proves that the pinned private dependency
resolves through the lazy facade, preserves raw bytes, emits ATIF-v1.7 and the
exact fail-closed check vocabulary, reports Harbor 0.18.0, and produces the
same bundle twice. The real-session E2E replays five size quantiles per agent
through the same facade; zero sessions skip that agent, while one to four fail
because they cannot substantiate five quantiles.

## Migration and rollback

The capability is additive. Rollback pins a prior known-good package commit or
removes the dependency, facade, recipes, tests, and this ADR together. Existing
evidence bundles remain self-describing ordinary files.

## Removal / supersession criteria

Supersede this ADR when a public package with equivalent raw preservation and
loss checks replaces the private library, or when the bundle contract changes
incompatibly.
