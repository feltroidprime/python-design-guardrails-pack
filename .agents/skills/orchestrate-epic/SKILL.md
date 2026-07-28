---
name: orchestrate-epic
description: Run or resume a compiled epic through the durable epicctl control plane and addressable Orca workers. Use when the user wants to dispatch, resume, or tear down multi-issue agent work with dependency readiness, model routing, SHA-bound checks and reviews, and guarded merge.
---

# Orchestrate an epic

`runtime/epicctl.py` is the acceptance authority. Orca is live transport; remote
Git preserves code; the hash-chained **journal** preserves readiness and
evidence. Read those three from their own sources, never from prose or a pane
transcript.

Compile the epic first with [`/plan-epic`](../plan-epic/SKILL.md); this skill
starts from a manifest.

## Runtime

The control plane is pure standard library, so it runs under a bare
interpreter. Only the compiler needs a dependency.

```text
RUNTIME=.agents/skills/orchestrate-epic/runtime
python3 $RUNTIME/epicctl.py --manifest MANIFEST --journal JOURNAL COMMAND
```

Put `MANIFEST` and `JOURNAL` in a **state worktree** — a checkout on its own
branch, separate from every worker lane — so control state and product code
never contend.

## Lean tree-and-leaf topology

- One thin coordinator; no standing foremen.
- Planner calls exist only at the root, a genuinely ambiguous internal node, or
  an opened decision gate. They emit structured trees or decisions and exit.
- One persistent economical worker per executable leaf until acceptance. Give
  it the root-to-parent goal path and its leaf contract, then load
  [`/epic-worker`](../epic-worker/SKILL.md).
- Novel leaves receive one fresh different-family
  [`/epic-reviewer`](../epic-reviewer/SKILL.md); mechanical leaves skip semantic
  review until risk is raised.
- Reuse the same worker terminal through implementation and fixes.

## Launch

Run every check below from a clean checkout, then drive the loop:

```text
python3 $RUNTIME/preflight.py --manifest MANIFEST
python3 $RUNTIME/epicctl.py --manifest MANIFEST --journal JOURNAL init
```

`preflight` fails on a dirty or stale checkout, missing `gh` auth, an
unreachable Orca, and on a guard hook that is anything other than silent with
no active envelope. That last one is why it exists: a hook launched by an
interpreter that cannot import its dependencies exits non-zero, and the harness
then blocks every worker's first edit.

## Drive only the durable next action

1. `ready` returns the dependency-, capacity-, barrier-, and lane-safe
   **frontier**. `status` adds the whole run.
2. Resolve the worker identity before creating a terminal, so the launch matches
   the manifest rather than an ambient default:

   ```text
   ... model-route --role worker --task TASK
   ... model-route --role reviewer --task TASK
   ```

   Use `--role planner` at the root and `planner-escalation` only at a gate.
3. Create the Orca task, worktree, and dispatch through the validated
   operations in [`references/orca-adapter.md`](references/orca-adapter.md);
   record the exact ids with `start`.
4. Materialize the worker **envelope** and inject `/epic-worker`.
5. Require an early remote checkpoint. `checkpoint` verifies the remote ref and
   leases the exact free out-of-lane paths found in the complete base...head
   diff, so a non-Claude worker gets the same scope behavior as a hook-guarded
   one.
6. Run each official `run-check` once at the clean pushed SHA. Downstream roles
   consume its **receipt** instead of repeating the command.
7. For novel work, issue one digest-bound review **packet** and record the
   structured verdict. A repeated finding fingerprint or the total-review
   ceiling opens a planner gate.
8. `accept` independently recollects the complete PR file set and the current
   required CI. The effective **lane** is the base lane plus durable exact-path
   leases.
9. `merge` records intent before the SHA-guarded GitHub mutation. On any
   uncertainty call `reconcile-merge`; a second blind merge request is how a
   double-merge happens.
10. Publish the control state after each mutation:

    ```text
    python3 $RUNTIME/state_sync.py STATE_WORKTREE
    ```

11. Recover from a restart with `recover --repos`, and resume from a proven
    remote checkpoint. Orca state alone never establishes that code survived.

## Ownership without live friction

A worker automatically leases one exact file when it is outside its base lane,
unprotected, and held by no other live task. The **lease** is journaled before
the write, appears in the envelope and review packet, expands acceptance scope,
and serializes future conflicting leaves.

Shared globs, generated bundles, migrations, and interface ownership changes go
to a planner instead.

## Finish

Finish only when every manifest leaf is merged, main-branch exit evidence is
green, control state is pushed, the Orca run is stopped, and every worktree is
inspected and removed. Confirm a remote merge before removing the worktree that
holds it.
