# ADR-0009: A projected document states the project, not the pack

- Status: accepted
- Date: 2026-08-06
- Owners: repository maintainers
- Revisit trigger: a starting file that repeats a fact the pack already owns,
  or a projected document that a reader of a Terminal Project cannot act on

## Context and forces

Terminal Projection copies the whole tracked tree, swaps the two identity
tokens, and overlays a few files with a starting version. Every other file
reaches a Terminal Project word for word.

Most of the tree survives that copy correctly. `pack/` describes machinery the
project keeps. `docs/adr/` records decisions the project inherits. A capability
directory is the project's own work.

Three documents do not survive it. `AGENTS.md`, `CONTEXT.md` and
`VALIDATION.md` state facts about the Root Pack, and a Terminal Project is not
the Root Pack.

- `AGENTS.md` teaches the capability layout from a worked example, and
  projection deletes that example. It also names an acceptance suite the
  project does not carry, and a second CI job the project does not run.
- `CONTEXT.md` defines Root Pack, One-shot Bootstrap and Terminal Projection. A
  Terminal Project is none of the three, and it cannot perform the operation
  the third one names.
- `VALIDATION.md` records a gate run on the maintainer's machine, dated before
  the project existed. `docs/README.md` calls that record dated, and its date
  is wrong from the first commit.

The documentation audit of 2026-08-06 found all three. A reader who follows any
one of them follows the wrong repository.

## Decision

The overlay covers every document whose subject is the pack itself.

`AGENTS.md`, `CONTEXT.md` and `VALIDATION.md` join `README.md`, `CHANGELOG.md`,
the quality workflow and the composition root as starting files. The overlay
now covers seven files. Every other file still reaches a Terminal Project with
the two identity tokens swapped and nothing else changed.

One rule decides that list.

> A file is a starting file when a reader of a Terminal Project would act
> wrongly on the pack's version of it.

The starting `VALIDATION.md` records no run. It states the shape of a record,
and it names the commands that produce one. A project writes its own record on
its first full gate run.

The pack keeps its own three documents, and it can now name its own capability
in them plainly. Before this decision, `REM-2` read the pack's `AGENTS.md`
inside every project the pack starts, so the pack could not write the path of
the directory it was teaching.

## Alternatives considered

- **Leave the three documents as they are.** Rejected, and measured. `REM-2`
  fails when `AGENTS.md` names the deleted capability by path, so the pack was
  already paying for this in prose it could not write plainly.
- **Delete the three from a Terminal Project.** Rejected. `docs/README.md`
  registers all three, and `DOC007` fails on a registry row with no file. A
  project that starts with no contract also starts with no rule a coding agent
  can read.
- **Edit the three inside the file at projection time.** Rejected. Step 2 is a
  blind two-token byte swap, and no template engine runs. An interior edit
  returns the pack to a template, which this repository removed.

## Consequences

### Positive

- A Terminal Project reads a contract that its own tree satisfies.
- The pack states its own machinery in its own words again.
- The `docs` hook of a Terminal Project reads all three documents at the root,
  so `DOC001` holds every path claim in them to the projected tree.

### Negative / cost accepted

- Three documents now exist in two versions. The pack version and the starting
  version can drift, and no hook compares them.
- `PAR-8` catches a starting file that was copied and never edited. It cannot
  catch one that went stale.

### Risks and mitigations

- *A starting document goes stale.* No hook of the pack reads the `initial`
  directory, so a defect there stays invisible until a project exists. `LEG-5`
  builds a real project and runs its whole gate, which reads the three
  documents at the root. Run the acceptance suite after any change to a
  starting file.

## Validation

`PAR-7` proves that each starting file shadows a file of the pack. `PAR-8`
proves that each one landed and differs from the file it replaced. `LEG-5` runs
the whole gate inside a projected project. `REM-2` proves that no document of
that project names the deleted capability.

## Migration and rollback

A project built before this change carries the pack's version of the three
documents. A Pack Update does not replace them, because all three are
user-owned. Replace them by hand from the `initial` directory of the release,
or leave them.

## Removal / supersession criteria

Supersede this decision if the overlay grows past the documents whose subject
is the pack. A starting version of a file that a project would edit anyway
belongs in the project, not in the pack.
