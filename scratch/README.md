# scratch — material that a later ticket owns

This directory is temporary. Ticket I1 collapsed the two trees into one Root Pack
tree. Some files had a REWRITE verdict whose target path does not exist yet. They
wait here until the ticket that owns them lands.

No tool reads this directory. Ruff, BasedPyright, pytest, and the gate all skip
it. The files hold retired vocabulary on purpose, so the LEG-1 and LEG-2 word
scans of #81 stay red until the last consumer removes this directory.

| File | Owed to | What it is |
|---|---|---|
| `agents-terminal-project.md` | I11 | The agent contract a new project starts from. |
| `readme-terminal-project.md` | I11 | The product document a new project starts from. |
| `hook_policy_tests.py` | I11 | Contract tests for the local hook routing of the gate. |

Ticket I8 took `bootstrap_pipeline.py` and `bootstrap_cli_tests.py`. The
pipeline is now `application/pipeline.py` of the capability, with the recipe
renamed to `setup` (C14) and `--no-github` and `--no-git` dropped (A3). The
ordering tests are now `tests/test_pipeline.py` of the same capability.

Ticket I9 took `pack_update_tests.py`. The proof that a pack operation never
rewrites a user-owned byte is now `tests/test_update.py` of the same capability,
against the Pack Update rather than against a Copier update. The Copier engine,
the declarations, and the derived indexes that file drove are all deleted.

Each consumer must delete the file it took. When the table is empty, delete this
directory.

Ticket I10 took `pack_validation.py`. The fault injection it carried is now the
acceptance suite at `src/guardrails_pack/bootstrap/tests/acceptance/`, which
runs from the installed console script instead of a source checkout. The same
ticket moved the five capability shapes to the fixtures of that suite.
