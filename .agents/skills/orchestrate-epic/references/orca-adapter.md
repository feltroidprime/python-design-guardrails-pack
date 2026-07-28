# Orca adapter

Keep these runtime operations separate from epicctl acceptance. Orca owns live
run/task/dispatch transport; the pushed journal owns durable acceptance.

Render every operation through `.agents/skills/orchestrate-epic/runtime/orca_adapter.py`. It reads one
structured JSON object from stdin and returns `{"argv": [...]}` without
executing Orca. Execute that argv as an argument array; do not rebuild it as a
shell string. For example, the input
`{"operation":"status","executable":"orca-ide"}` renders
`["orca-ide","status","--json"]`. Invalid selectors, guessed fields, wrong
target concepts, and undocumented task statuses fail before execution.

Replace `ORCA` in each command with one executable and keep it fixed: use
`orca` inside an Orca-managed terminal, `orca-ide` on Linux outside one, or the
value supplied by `ORCA_CLI_COMMAND`. `ORCA` is a documentation placeholder,
not a shell variable. Always copy opaque ids and handles from JSON responses.

## Start or recover the run

```text
ORCA status --json
ORCA worktree current --json
ORCA orchestration task-list --brief --json
ORCA orchestration run --spec "<compact epic run contract>" --max-concurrent <n> --worktree <state-worktree-selector> --json
```

`orchestration run` returns immediately. Record its run id in durable state. If
a live run already exists, inspect it rather than starting a duplicate. Stop it
only after the epic reaches a terminal state:

```text
ORCA orchestration run-stop --json
```

Do not mix two coordinators. In managed mode, the coordinator created by
`orchestration run` performs the task/dispatch operations below. In manual
recovery mode, omit `orchestration run` and perform them directly. Never create
a manual task or dispatch when `task-list`/`dispatch-show` already records it.

## Create and dispatch one persistent issue worker

Create a separate checkout only because parallel issue lanes require it. Prefer
agent-first creation when its built-in launcher satisfies the manifest pin:

```text
ORCA worktree create --repo <repo-selector> --name <task-name> --no-parent --agent <agent-id> --json
ORCA terminal wait --terminal <startupTerminal.handle> --for tui-idle --timeout-ms 120000 --json
```

When exact model argv requires a custom command, use the returned full
`<repoId>::<worktreePath>` id and target only the new agent terminal:

```text
ORCA worktree create --repo <repo-selector> --name <task-name> --no-parent --json
ORCA terminal create --worktree id:<repoId>::<worktreePath> --title <task-name> --command '<manifest-pinned-worker-command>' --json
ORCA terminal wait --terminal <handle> --for tui-idle --timeout-ms 120000 --json
```

Create a tracked task and inject exactly one compact envelope:

```text
ORCA orchestration task-create --spec "<compact task packet>" --deps <json_array> --json
ORCA orchestration dispatch --task <task_id> --to <handle> --inject --json
ORCA orchestration dispatch-show --task <task_id> --json
```

Use the same worker through implementation and fixes. Do not create a new
worker for each edit or test.

## Wait, decide, and review

```text
ORCA orchestration check --wait --types worker_done,escalation,decision_gate --timeout-ms 900000 --json
ORCA orchestration ask --to <coordinator_handle> --question "<bounded question>" --options <csv> --timeout-ms 900000 --json
ORCA orchestration reply --id <message_id> --body "<decision>" --json
```

A timeout is a checkpoint. Continue rolling waits while the terminal exists and
shows activity. Use `task-update` only for explicit recovery or override; valid
`worker_done` completes the active dispatch automatically:

```text
ORCA orchestration task-update --id <task_id> --status blocked --result <json> --json
```

For novel work, start a fresh different-family reviewer terminal in the PR
worktree, create a child review task, and dispatch a compact pinned-SHA packet:

```text
ORCA terminal create --worktree id:<repoId>::<worktreePath> --title review-<task> --command '<manifest-pinned-reviewer-command>' --json
ORCA terminal wait --terminal <review_handle> --for tui-idle --timeout-ms 120000 --json
ORCA orchestration task-create --spec "<pinned-SHA review packet>" --parent <implementation_task_id> --json
ORCA orchestration dispatch --task <review_task_id> --to <review_handle> --inject --json
```

Do not use a lifecycle Agent-tool subagent or a worker-family reviewer.

Mirror exceptional decisions into native gates:

```text
ORCA orchestration gate-create --task <task_id> --question "<bounded decision>" --options <json_array> --json
ORCA orchestration gate-list --task <task_id> --json
ORCA orchestration gate-resolve --id <gate_id> --resolution "<decision>" --json
```

Apply the same decision to epicctl; an Orca gate alone is not acceptance.

## Complete and tear down

Send `worker_done` exactly once from the dispatched worker's own terminal with
the active task and dispatch ids:

```text
ORCA orchestration send --to <coordinator_handle> --type heartbeat --subject alive --payload '{"taskId":"<task_id>","dispatchId":"<dispatch_id>","phase":"<phase>"}' --json
ORCA orchestration send --to <coordinator_handle> --type worker_done --subject "<status>" --body "<concise evidence summary>" --payload '{"taskId":"<task_id>","dispatchId":"<dispatch_id>","filesModified":["path"],"reportPath":"<optional>"}' --json
```

After epicctl accepts and records the observed merge, verify the remote merge
first. Then inspect and remove the exact worktree:

```text
ORCA worktree show --worktree id:<repoId>::<worktreePath> --json
ORCA terminal stop --worktree id:<repoId>::<worktreePath> --json
ORCA worktree rm --worktree id:<repoId>::<worktreePath> --force --json
```

Never remove a worktree containing the only copy of unpushed work.
