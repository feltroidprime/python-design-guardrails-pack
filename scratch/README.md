# scratch — material that a later ticket owns

This directory is temporary. Ticket I1 collapsed the two trees into one Root Pack
tree. Some files had a REWRITE verdict whose target path does not exist yet. They
wait here until the ticket that owns them lands.

No tool reads this directory. Ruff, BasedPyright, pytest, and the gate all skip
it. The files hold retired vocabulary on purpose, so the LEG-1 and LEG-2 word
scans of #81 stay red until the last consumer removes this directory.

| File | Owed to | What it is |
|---|---|---|
| `pack_validation.py` | I10 | The fault-injection half of the deleted pack validation script. |
| `pack_update_tests.py` | I9 | The proof that a pack operation never rewrites a user-owned byte. |
| `ownership_surface_tests.py` | I2 | The proof that the pack writes no user-owned file. |

Ticket I8 took `bootstrap_pipeline.py` and `bootstrap_cli_tests.py`. The
pipeline is now `application/pipeline.py` of the capability, with the recipe
renamed to `setup` (C14) and `--no-github` and `--no-git` dropped (A3). The
ordering tests are now `tests/test_pipeline.py` of the same capability.

Each consumer must delete the file it took. When the table is empty, delete this
directory.

The five capability shapes stay at `tests/fixtures/shapes/`. Ticket I10 moves
them to the acceptance fixtures of the bootstrap capability.
