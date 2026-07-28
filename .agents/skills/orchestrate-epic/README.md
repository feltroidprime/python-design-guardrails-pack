# Epic orchestration — human guide

Four skills and one vendored control plane for running a large piece of work
across several agents at once, without losing track of what was actually
verified.

This file is for you, not the agent. The agents read the `SKILL.md` files.

| Skill | Who runs it | What it does |
|---|---|---|
| `/plan-epic` | you | spec or PRD → a compilable `epic.yaml` → `manifest.json` |
| `/orchestrate-epic` | you | drives the run: dispatch, checks, review, merge, teardown |
| `/epic-worker` | a worker agent | implements one leaf until its SHA is accepted |
| `/epic-reviewer` | a reviewer agent | judges one leaf at a pinned SHA |

You invoke the first two. The coordinator injects the other two into the
terminals it creates.

## The problem it solves

Running several coding agents in parallel fails in specific ways: two agents
edit the same file, an agent claims a test passed that never ran, a crash loses
which work was real, and a reviewer that read the whole conversation just
agrees with the author.

The control plane answers each of those with durable state rather than trust:

- **journal** — an append-only, hash-chained log with optimistic locking. Task
  state is a pure fold over it, so readiness is derived, never remembered. It
  survives any crash and detects tampering.
- **lane / lease** — each task owns a set of paths. A file discovered outside
  that lane is leased exactly, before the write, and only if no other live task
  holds it. Protected paths are refused.
- **receipt** — a check is run once, at a clean pushed SHA, and recorded. Later
  roles read the receipt instead of rerunning or claiming.
- **packet** — a reviewer gets a compact SHA-pinned bundle, not the transcript,
  so its verdict is independent of the author's reasoning.
- **frontier** — `ready` computes what may start now from dependencies,
  capacity, barriers, and live lane ownership.

## Requirements

- **Orca** — live transport for worktrees, terminals, and dispatch. The
  coordinator needs `orca`, `orca-dev`, or `orca-ide` on `PATH`, or
  `ORCA_CLI_COMMAND` set.
- **`gh`**, authenticated — GitHub is the evidence authority for PR files, CI,
  and the guarded merge.
- **`git`** with a writable remote.
- **Python 3.14** — the version this is developed and tested against. The
  control plane is pure standard library, so it needs no virtualenv.
- **`uv`** — only for `compile_epic.py`, which needs `yamlrocks`.

## Install into another repository

Copy the four skill directories; the runtime travels inside
`orchestrate-epic/`, and the relative paths between the skills keep working.

```bash
SRC=/path/to/python-design-guardrails-pack/.agents/skills
mkdir -p .agents/skills
cp -R "$SRC"/{plan-epic,orchestrate-epic,epic-worker,epic-reviewer} .agents/skills/

# Claude Code reads .claude/skills; Codex reads .agents/skills directly.
mkdir -p .claude/skills
for skill in plan-epic orchestrate-epic epic-worker epic-reviewer; do
  ln -sfn "../../.agents/skills/$skill" ".claude/skills/$skill"
done
```

Verify the control plane runs before planning anything:

```bash
python3 .agents/skills/orchestrate-epic/runtime/epicctl.py --help
```

## Running an epic

**1. Plan it.** Invoke `/plan-epic` with your spec or PRD. It writes an
`epic.yaml` and compiles it:

```bash
uv run --no-project --with yamlrocks python \
  .agents/skills/orchestrate-epic/runtime/compile_epic.py epic.yaml \
  --output manifest.json --summary
```

The compiler rejects an unresolvable dependency graph, a leaf missing from the
goal tree, and open-ended acceptance evidence. A file that compiles is not
automatically a good plan — read the leaf set yourself before spending tokens on
it.

**2. Give the control state its own worktree.** Keep `manifest.json` and the
journal on a separate branch so control state and product code never contend:

```bash
git worktree add -b orchestration/my-epic ../my-epic-state origin/main
mkdir -p ../my-epic-state/.orchestration
cp manifest.json ../my-epic-state/.orchestration/
```

**3. Preflight, then initialize.**

```bash
RUNTIME=.agents/skills/orchestrate-epic/runtime
STATE=../my-epic-state/.orchestration

python3 $RUNTIME/preflight.py --manifest $STATE/manifest.json
python3 $RUNTIME/epicctl.py \
  --manifest $STATE/manifest.json --journal $STATE/journal.ndjson init
```

Preflight refuses a dirty or stale checkout, missing `gh` auth, an unreachable
Orca — and a guard hook that is anything but silent. That last check exists
because a hook launched by an interpreter missing its dependencies exits
non-zero, and the agent harness then blocks every `Edit`/`Write`. Without the
check, the run dies on the first worker edit instead of here.

**4. Run it.** Invoke `/orchestrate-epic` from a planner terminal opened in the
state worktree. It drives `ready` → `start` → `checkpoint` → `run-check` →
review → `accept` → `merge`, publishing state after each mutation.

**5. Resume.** The journal is the run. After any crash or restart:

```bash
python3 $RUNTIME/epicctl.py --manifest ... --journal ... recover --repos ...
```

Resume from a proven remote checkpoint. Orca state alone never establishes that
code survived — only the remote does.

## Useful commands

All take `--manifest MANIFEST --journal JOURNAL` first.

| Command | Purpose |
|---|---|
| `init` | seed the journal from the manifest |
| `ready` / `status` | the dispatchable frontier / the whole run |
| `model-route --role worker --task T` | resolve the launch identity for a task |
| `start T ...` | record a dispatch with its exact Orca ids |
| `checkpoint T ...` | verify the remote ref, lease discovered paths |
| `run-check T --name N` | create the one official receipt for a check |
| `review-packet T` / `record-review T` | issue a packet / record a verdict |
| `lease-request T --path P` | acquire one exact out-of-lane path |
| `accept T` / `merge T` | recollect evidence / guarded merge |
| `recover --repos` | reclassify live tasks after a restart |

## Honest limits

- **Exact-file leases do not solve semantic conflict.** Two tasks editing
  different files can still contradict each other.
- **Model launch requests are provenance, not proof.** Nothing here verifies a
  provider actually served the model you asked for.
- **Git and the state branch preserve code and evidence**, but total host and
  remote loss still needs an independent mirror.
- **The transport is Orca-specific.** The acceptance layer (`epicctl`,
  `compile_epic`, `github_evidence`) is not, and can be driven by hand.
- **Effective parallelism is the plan's property, not the tool's.** A nearly
  linear dependency chain runs nearly serially no matter how many workers are
  allowed.

## Provenance

Vendored from the orchestration harness in
[`feltroidprime/conductor`](https://github.com/feltroidprime/conductor)
(`orchestration/`), where it has its own test suite. The vendored copy drops the
epic-specific evidence collector and the repo-specific bootstrap; everything
else is byte-identical apart from the import fallbacks that let the modules run
outside their original package.

To refresh, re-vendor from upstream rather than editing here, so the two copies
do not diverge.
