---
name: plan-epic
description: Turn a spec, PRD, or large objective into the normalized epic.yaml the durable orchestration control plane consumes. Use when the user wants work decomposed into dispatchable agent tasks, or when another skill needs a compiled epic manifest.
---

# Plan a normalized epic

Read [`EPIC-SPEC.md`](EPIC-SPEC.md) for the source format. Produce one versioned
`epic.yaml` — a closed, compilable artifact rather than a prose epic or a fixed
three-tier organization chart.

One `epic.yaml` per coherent objective. A spec that carries two independent
outcomes compiles into two epics, each with its own manifest and run.

1. State one externally observable epic outcome, measurable success conditions,
   and explicit non-goals.
2. Build a variable-depth **goal tree**. Internal nodes own shared decisions;
   executable work appears exactly once, as leaves.
3. Keep the dependency DAG separate from the goal tree. Tree ancestry controls
   context; `depends_on` controls readiness.
4. Give each leaf an outcome, decision boundary, interfaces, uncertainty, risk,
   expected base **lane**, hard forbidden paths, closed acceptance evidence, and
   exact checks.
5. Keep lanes broad — they predict conflict. The runtime acquires exact free
   paths as durable scope **leases** when implementation discovers them.
6. Route novel coding to a strong reasoning model and bounded mechanical work to
   a cheaper one, and review each with a different model family, so a shared
   blind spot cannot pass its own work.
7. Leave distant high-uncertainty work undecomposed. Create a discovery leaf
   whose output is evidence or a decision, then plan the successor epoch from
   what it returns.
8. Compile it:

   ```text
   uv run --no-project --with yamlrocks python \
     .agents/skills/orchestrate-epic/runtime/compile_epic.py epic.yaml \
     --output manifest.json --summary
   ```

The compiler rejects an unresolvable DAG, a leaf missing from the tree, and
open-ended evidence. It cannot judge whether the decomposition is good, so read
the leaf set once more and cut implementation guesses, duplicated decisions,
evidence a reviewer could not close, and any leaf too large for one persistent
worker context.

Hand the manifest to [`/orchestrate-epic`](../orchestrate-epic/SKILL.md).
