# Manifest contract

New epics start from `../../plan-epic/EPIC-SPEC.md` and are compiled by
`../runtime/compile_epic.py`. The source separates outcome tree, dependency
DAG, decision ownership, evidence, model profiles, and expected lanes.

The immutable compiled manifest adds:

- one goal-tree leaf per task;
- exact argv checks;
- `model_profiles` and `model_routing`;
- per-task `worker_profile` / `reviewer_profile`;
- base lanes and hard forbidden paths;
- optional initial merged state and successor-epoch lineage.

Once a journal is initialized, do not edit its manifest. A planner re-split
creates the immediate successor epoch and cites the predecessor digest.
