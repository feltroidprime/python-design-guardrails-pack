# ADR-0008: Two ownership surfaces, stated as one predicate

- Status: accepted
- Date: 2026-08-05
- Owners: repository maintainers
- Revisit trigger: a path that the predicate classifies wrongly, or a third
  surface that a real update operation needs

## Context and forces

An update of the pack replaces infrastructure inside a project that is already
in use. It must never write a file that the owner wrote. ADR-0007 answered that
with four classes and a list of about forty roots, plus three hand-written
validators. A list cannot answer for a path that nobody has written yet, and
two of the four classes described artifacts that are now deleted.

A coding agent needs the same answer, for any path, without reading a list.

## Decision

Two surfaces, and one predicate states both.

> **Pack-owned** is the `pack/` directory at the repository root, plus
> `_`-prefixed names and `py.typed` inside `src/<package>/`.
> **User-owned** is everything else.

```python
def pack_owned(rel: str, pkg: str) -> bool:
    parts = rel.split("/")
    if parts[0] == "pack":
        return True
    if parts[:2] == ["src", pkg] and len(parts) > 2:
        return parts[2].startswith("_") or parts[2] == "py.typed"
    return False
```

`pack/scripts/ownership.py` holds that function, and it is the only ownership
code in the tree. Every planned write of an update is checked against it, per
path, and never against a list of paths. A file that a new release dropped is
absent from any list, and the update must still delete it.

Four user-owned files at the root are thin entry points into `pack/`: the
`justfile`, `pyrightconfig.json`, `.python-version`, and the quality workflow.
An update reports a suggested change to each one and never writes it.

**Exception granted.** `pack/tests/test_gate_definition.py` and
`pack/tests/unit/scripts/test_ownership.py` read the tracked tree with
`git ls-files -z` through `subprocess.run`, and each call carries `noqa: S603`
with the marker `ARCH-EXCEPTION: ADR-0008`. The predicate answers for a real
tracked tree or it answers for nothing, and `git` is the only source of that
tree. The command is a fixed constant with no input from a caller.

## Alternatives considered

- **Keep four classes and shorten the list.** Rejected: the list stays a list,
  and it still cannot answer for an unwritten path.
- **A marker file inside each pack-owned directory.** Rejected: a marker is
  state that can drift from the tree it describes.
- **Derive ownership from the manifest.** Rejected, and measured: a manifest
  holds the paths of one release, so it cannot express a deletion.

## Consequences

### Positive

- Any reader classifies any path in one step, with no list to consult.
- An update writes only what the predicate admits, including a deletion.
- Three hand-written validators and about forty root entries are deleted.

### Negative / cost accepted

- The rule is positional: a pack-owned file must sit under `pack/`, or its name
  must start with `_`. There is no way to mark one exception.

### Risks and mitigations

- *One stray edit to a pack-owned file blocks every later update* until a human
  reverts it or passes `--force`. The refusal names the file, and `--force`
  saves the replaced bytes in a backup directory under `pack/`, which a
  pack-owned ignore rule keeps out of git.

## Validation

`pack/tests/unit/scripts/test_ownership.py` states the Pack-owned Surface a
second time as a text rule and compares it with the predicate over every
tracked path. `pack/tests/test_gate_definition.py` proves that no pack-owned
file carries an identity token.

## Migration and rollback

The one-tree refactor of 2026-08-05 introduced both surfaces at once. There is
no partial state to roll back to.

## Removal / supersession criteria

Supersede this decision only with a classifier that is equally short, equally
positional, and able to express a deletion.
