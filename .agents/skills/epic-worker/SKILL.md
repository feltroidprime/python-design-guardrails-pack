---
name: epic-worker
description: Implement and repair one executable epic leaf from its durable task envelope. Use in the persistent worker terminal assigned to that leaf, until its pushed SHA is accepted.
---

# Execute one epic leaf

Treat `.orchestration/task-envelope.json` and the injected `SessionStart`
`next_action` as current authority. An older prompt is advisory.

1. Confirm the task, pinned base, root-to-parent `goal_path`, outcome,
   `decision_boundary`, interfaces, **lane**, active scope **leases**, hard
   forbidden paths, acceptance criteria, and required checks.
2. Make task-local implementation decisions yourself. Escalate only when a
   choice changes an ancestor decision, a sibling interface, a protected
   contract, an irreversible resource, the epic purpose, or a hard budget.
3. Implement, and run focused development tests as you go.
4. Commit and push the first coherent checkpoint early, even while red, and
   again after each meaningful fix. Unpushed work is disposable — the remote is
   what survives a crash, not the worktree.
5. A base lane predicts conflict rather than prophesying it. On the first write
   to a free out-of-lane file a Claude hook acquires the exact-path lease; from
   another client, request it:

   ```text
   python3 .agents/skills/orchestrate-epic/runtime/epicctl.py \
     --manifest MANIFEST --journal JOURNAL \
     lease-request TASK --path PATH --reason REASON --expected-seq SEQ
   ```

   A protected path, or one held by another live task, is a hard stop: report it
   and continue with the rest of the leaf. Broad globs, generated mutex outputs,
   and sibling-interface changes are planner decisions, not a series of
   exact-file leases.
6. Let `epicctl run-check` create the one official **receipt** per check and
   pushed SHA. Local runs inform your work; the receipt is the evidence.
7. Open or update the PR. Report its number, the pushed SHA and ref, the
   development tests you ran, remaining risks, and any scope you discovered.
   File and CI evidence is collected independently of your report.
8. On rejection, keep this same terminal and fix the structured findings in the
   refreshed envelope. A changed SHA invalidates the prior review packet.

Stay inside the leaf: the grader, the merge, and the worktree lifecycle belong
to the coordinator, and untracked subagents make work no one can attribute.

Send one dispatch-scoped `worker_done` once the requested checkpoint or fix is
pushed, then idle. Acceptance is the control plane's to declare.
