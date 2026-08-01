# Prototype — external init and update protocol (ticket #82)

Throwaway. Run `python3 prototype/init-update-protocol/proto_update.py all`.
49 measurements against real files and real git. Nothing is mocked.

## The protocol under test

### CLI — two functions, both external

```
pyrepo bootstrap init   <name> [directory]
pyrepo bootstrap update [directory]        # directory defaults to .
```

Both are functions of the One-shot Bootstrap capability, so they follow #89's
`<project> <capability> <function>` line without an exception. Projection deletes
that capability directory, so a Terminal Project has neither subcommand and ships
no updater code. The updater is always a *newer installed pack* acting on a
directory from outside.

### Provenance — one generated pack-owned file

`pack/manifest.json`, written at build time, shipped inside `_pack.tar`, projected
verbatim:

```json
{
  "pack_version": "0.4.0",
  "root":    {"pack/scripts/quality_gate.py": "<sha256>", "...": "..."},
  "package": {"_foundation/router.py": "<sha256>", "py.typed": "<sha256>"},
  "shims":   {".github/workflows/quality.yml": "<sha256>", "...": "..."}
}
```

Two path lists rather than one, so **no identity token and no placeholder markup
appears in the file**: `root` paths are literal, `package` paths are relative to
`src/<pkg>/`, whose name the update derives from the destination. The manifest
therefore satisfies #86's invariant outright and is itself pack-owned.

`shims` records the *as-shipped* hash of the user-owned entry points. The update
never writes them; it uses the hashes to tell a customised shim from an untouched
one, so the report only nags where it can help.

Rejected alternative: no manifest, and detect drift by re-projecting the recorded
version from a downloaded old wheel. It needs the network, a cache, and a version
that is still on PyPI. The manifest costs one generated file.

### Update — eight steps, no rendering, no interior edit

```
1. read pack/manifest.json in the destination      -> old version, old hashes
2. read pack/manifest.json in the installed pack   -> new version, new hashes
3. refuse (U1-U8 below)
4. classify every pack-owned path: ADD / REPLACE / DELETE / UNCHANGED
5. hash the destination's pack-owned files -> drift
6. apply the drift policy
7. snapshot, write, restore on any failure; write the manifest LAST
8. print the shim report; write no user-owned file
```

The only identity-aware step is deriving `src/<pkg>/` from the destination.

### Version transition

Forward only, one jump of any distance. `0.2.0 -> 0.7.0` is one operation because
the new pack fully describes the new pack-owned surface; nothing accumulates per
version. Equal version is a no-op that exits 0. Lower version is refused (U3).

**No migration code ever ships.** When a release needs a user-owned change, the
update prints it and the human applies it. That is the direct price of shipping no
updater code downstream, and it is why the shim surface must stay tiny.

## Measured results

### Invariant — two projections, one pack-owned surface

| Measure | Result |
|---|---|
| pack-owned files byte-identical across `my-product` and `other-thing` | 10 of 10 |
| pack token inside a pack-owned file | 0 |
| `pack/manifest.json` identical across the two projects | yes |
| user-owned root files the update may never touch | 8 |

### Update 0.3.0 -> 0.4.0 (one add, one replace of a script, one delete, one router change)

| Measure | Result |
|---|---|
| classification add / replace / delete / unchanged | 1 / 3 / 1 / 7 |
| paths written | 5 |
| user-owned files changed | 0 |
| file deleted by the new version, gone from disk | yes |
| file added by the new version, present | yes |
| version the project claims afterwards | 0.4.0 |
| second run | 0 paths, idempotent |

### Drift — the user edited two pack-owned files, one of which v0.4.0 also changes

| policy / scope | outcome | user's edit survives | recoverable copy | manifest disagrees with disk |
|---|---|---|---|---|
| refuse / written | refused on 1 file, 0 changes | yes | git | — |
| skip / written | wrote 4 paths | yes | git | **2 files** |
| backup / written | wrote 5 paths | no | `pack/.drift/…` | **1 file** |
| refuse / all | refused on 2 files, 0 changes | yes | git | — |
| backup / all | wrote 6 paths | no | `pack/.drift/…` | 0 files |

**Scope matters more than policy.** A file the user edited that the new version
does *not* change is invisible to any `written`-scope rule, so the manifest ends
up describing a tree that no longer exists — even under `backup`. Only `all`
scope leaves the manifest true.

### Refusals — every rule fires against a real tree

| # | Rule | Fired |
|---|---|---|
| U1 | no `pack/manifest.json` — not a Terminal Project | yes |
| U2 | `src/` holds 0 or 2+ directories — cannot derive the package | yes |
| U3 | the project records a newer version than the installed pack — downgrade | yes |
| U4 | not a git repository | yes |
| U4 | the git worktree is dirty | yes |
| U5 | a pack-owned file drifted | yes |
| U6 | the plan would write a path the ownership predicate forbids | yes (never triggered by a correct plan) |
| U7 | a bootstrap capability is present — the destination is a Root Pack | yes |
| U8 | the installed pack's own manifest is stale against its tree | yes |
| — | equal version | 0 paths, exit 0, not a refusal |

### Recovery — a crash mid-write

| Measure | Result |
|---|---|
| crash injected after | 2 of 5 writes |
| tree afterwards | byte-identical to before |
| `git status --porcelain` afterwards | 0 entries |
| retry | wrote 5 paths, succeeded |
| `git checkout -- . && git clean -fd` after a good update | restores 0.3.0 |

The transaction and git do different jobs. The snapshot-and-restore covers the
*interrupted* run, where git would otherwise leave the user a half-written tree to
clean up by hand. The clean-worktree rule covers the *completed but unwanted* run,
and it is why no `pyrepo bootstrap undo` needs to exist.

### Shims — user-owned entry points

| Case | pack changed the shim | flagged as customised | rewritten by update |
|---|---|---|---|
| user never touched their shim | yes | no | no |
| user customised their shim | yes | yes | no |

The pack changed `actions/checkout@v4` to `@v5`. This is the rot #86 predicted, and
the report is the whole mitigation.

### Distribution — through a real tar blob

51200-byte blob, 24 files. The update driven from the extracted blob wrote the same
5 paths and produced the same 0.4.0. #80's packaging holds for `update`, not only
for `init`.

## Three corrections the prototype forced

1. **#83's substitution rule is wrong.** It says "whole-word replacement across
   every projected text file, plus **one** directory rename (`src/<package>/`)".
   `bootstrap/initial/src/<pkg>/composition.py` is a second occurrence: leave its
   path alone and the overlay shadows nothing, and R9 fires on a valid pack. The
   rule must read **rename every path component equal to a pack token**. Measured:
   2 renames per projection, not 1.

2. **The manifest cannot hash itself, so the diff never contains it.** Without an
   explicit final write the update leaves the project claiming its old version and
   repeating the same writes for ever — measured before the fix as "0.3.0" and
   "NOT idempotent". The manifest is written last, inside the transaction. The
   honest cost: the manifest is the one pack-owned file whose integrity is not
   self-attested, so a hand-edited manifest fools drift detection. Git records the
   edit; nothing else does.

3. **The write rule must be the predicate, never the manifest's path list** —
   #86 said so, and a deletion proves why. A file the new version dropped is
   absent from the new manifest, yet the update must still remove it. The list
   describes what the pack *ships*; the predicate describes what the update *may
   touch*. U6 asserts the predicate over every planned write.

## Open, and deliberately not decided here

- The drift policy and its scope. The table above is the evidence; the choice is a
  product call.
- Whether `update` requiring a clean git worktree is acceptable as the only undo.
