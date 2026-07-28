# Normalized epic input

The most efficient epic input is **not** a long issue body and not a fixed list
of implementation tickets. It is one versioned document that separates four
things agents otherwise conflate:

1. **Outcome tree** — what must become true and why.
2. **Execution DAG** — which executable leaves depend on which completed work.
3. **Decision ownership** — what a leaf may decide locally versus what belongs
   to an ancestor planner node.
4. **Evidence contract** — what observable result and checks close each leaf.

`.agents/skills/orchestrate-epic/runtime/compile_epic.py` validates this source and emits the immutable
manifest consumed by `epicctl`.

## Schema

```yaml
schema_version: 1

run:
  id: owner-repo-epic-123-v1
  epoch: 1
  predecessor_manifest_digest: null
  source_main_sha: 40-hex-sha
  base_ref: main
  max_concurrent: 2
  max_same_finding_rejections: 2
  max_review_rejections: 4
  require_ci: true

epic:
  id: owner/repo#123
  outcome: One externally observable sentence.
  success_metrics:
    - A measurable exit condition.
  non_goals:
    - A tempting adjacent project that is explicitly excluded.

models:
  planners:
    opus:
      family: anthropic
      model: claude-opus-5
      effort: xhigh
    sol:
      family: openai
      model: gpt-5.6-sol
      effort: max
  workers:
    sonnet:
      family: anthropic
      model: claude-sonnet-5
      effort: xhigh
    terra:
      family: openai
      model: gpt-5.6-terra
      effort: max
  reviewers:
    sol:
      family: openai
      model: gpt-5.6-sol
      effort: max
    opus:
      family: anthropic
      model: claude-opus-5
      effort: xhigh
  routing:
    planner_primary: opus
    planner_escalation: sol
    worker_default: sonnet
    worker_by_risk:
      mechanical: terra
      novel: sonnet
    reviewer_by_worker:
      sonnet: sol
      terra: opus

checks:
  - name: unit
    command: [uv, run, pytest, -q]

protected_paths:
  - graders/**
no_go_paths:
  - external-corpus/**
barriers: []

goal_tree:
  id: epic
  goal: The epic outcome.
  children:
    - id: foundation
      goal: Establish the shared contract once.
      children:
        - id: task-foundation
          task: foundation
    - id: delivery
      goal: Deliver independent behavior leaves.
      children:
        - id: task-feature
          task: feature

tasks:
  foundation:
    repo: owner/repo
    issue: owner/repo#124
    outcome: The shared interface exists and one real path uses it.
    decision_boundary: May choose local representation; may not change epic semantics.
    interfaces: [public-api-v1]
    uncertainty: high
    depends_on: []
    risk: novel
    lane: [src/foundation/**]
    forbidden_paths: [graders/**]
    acceptance_criteria:
      - One real scenario executes through the shared interface.
    required_checks: [unit]
    done_artifacts: [src/foundation/api.py]

  feature:
    repo: owner/repo
    issue: owner/repo#125
    outcome: The user-visible feature works end to end.
    decision_boundary: May decide task-local implementation details.
    interfaces: [public-api-v1]
    uncertainty: low
    depends_on: [foundation]
    risk: mechanical
    lane: [src/feature/**]
    forbidden_paths: []
    acceptance_criteria:
      - The externally observable feature passes its focused test.
    required_checks: [unit]
    done_artifacts: [src/feature/implementation.py]
```

## Why this format is efficient

### Outcome first

Each branch and leaf begins with a result, not a requested implementation.
Workers can take the shortest correct path without treating an early guess as
an API commitment.

### Trees and DAGs stay separate

The goal tree controls context. A worker receives only its root-to-parent goal
path and leaf contract. Dependencies control readiness. Tree position never
silently creates execution order.

### Decisions have one owner

Shared design choices live at internal planner nodes. A leaf's
`decision_boundary` explicitly names what it can decide. This prevents two
workers from independently solving the same architecture question and then
forcing a late merge.

### Uncertainty remains visible

`uncertainty: high` means the leaf is expected to discover facts. It does not
justify a resident expensive agent. The planner returns only at a real ancestor
decision gate or when a leaf must be split into a successor epoch.

### Lanes are hints, leases are reality

`lane` is the expected diff, useful for initial parallelization. It is not a
perfect prophecy. Exact free paths discovered during implementation are
journaled as live scope leases. Protected paths and concurrent conflicts remain
hard stops.

### Models follow token economics

The primary planner is used only for root decomposition, ambiguous shared
nodes, and opened gates. Most tokens are spent by persistent leaf workers.
Mechanical tasks can route to Terra; novel implementation defaults to Sonnet.
Review is decorrelated by family. GPT-Sol receives structured packets rather
than emphatic free-form instructions, avoiding the literal-prompt sensitivity
observed in the benchmark audit.

## Long epics and increasing uncertainty

Do not fully pre-decompose distant uncertain work. Use one discovery leaf whose
outcome is a decision/evidence artifact. Once merged, the planner creates a
successor manifest epoch containing the newly justified leaves. The previous
manifest and journal remain immutable and reserve exactly one successor.

This gives long epics a stable history without freezing tomorrow's task graph
from today's incomplete knowledge.

## GitHub issues

For a new epic, generate or update issue bodies from this source rather than
making issue prose the only schema. An issue should contain:

- outcome;
- context and non-goals needed by that leaf;
- closed acceptance evidence;
- decision boundary;
- dependencies;
- expected lane and hard forbidden paths;
- a machine-readable dispatch block.

Repository-specific adapters may bind live issue state and closing PR evidence
into the compiled manifest. The generic control plane does not need to know the
epic number or repository.
