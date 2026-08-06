# Validation record — not yet run

This repository records no gate run. It starts from a projection, and the
record of the run that validated the Root Pack stays with the Root Pack.

`AGENTS.md` requires a fresh record after a gate run that follows a material
change. Replace this whole file with that record. Keep the four sections
below, and date the heading.

## Change validated

State the change in one paragraph, then list each defect the run covered. Name
the file, the rule and the observed behavior. A reader must be able to repeat
the finding without asking you a question.

## Evidence

Run these commands from the repository root, in this order.

```bash
just manifest
just check
just prove
```

Report the actual result of each one, copied from the terminal.

| Command | Result |
|---|---|
| `just manifest` | |
| `just check` | |
| `just prove` | |

`just manifest` is needed only after you edit a pack-owned file. Record the
whole gate as a pass or a fail. A hook that fails belongs here word for word,
and a narrower claim is a wrong claim.

## Remaining risks and portability notes

State every risk the run did not remove. State the operating system, the
Python version and the tool versions the run used. A record with no
environment proves nothing on another machine.

## What the projection already proved

The Root Pack ran its own gate and its own acceptance suite before it built
this repository. That evidence covers `pack/` and the structure of this tree.
It covers no product code, because this repository started with none.
