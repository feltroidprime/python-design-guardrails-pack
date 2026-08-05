"""One Pack Update: eight steps, eight refusals, and no user-owned byte.

```
1. read pack/manifest.json in the destination      -> old version, old hashes
2. read pack/manifest.json in the installed pack   -> new version, new hashes
3. refuse (U1-U8)
4. classify every pack-owned path: ADD / REPLACE / DELETE / UNCHANGED
5. hash the destination's pack-owned files          -> drift
6. apply the drift policy
7. snapshot, write, restore on any failure; write the manifest LAST
8. print the shim report; write no user-owned file
```

The only identity-aware step is deriving `src/<pkg>/` from the destination
(#85 section 3.5). Nothing here renders, and nothing here runs the gate: an
update carries the current tool policy, writes no user-owned file, and exits 0.
A red gate on user code afterwards is the intended signal, not a refusal
(conflict C13 of #85). Git is the undo, so the update refuses a dirty worktree.

A version transition is forward-only and takes one jump. An equal version writes
zero paths and exits 0, a lower version is refused, and no migration code ever
ships. When a release needs a user-owned change, the report names it and a human
applies it.

The drift policy is refuse-all. `--force` overwrites, and it saves the bytes it
replaces under `pack/.drift/<path>`, which the pack-owned `pack/.gitignore`
keeps out of git (conflict C11 of #85).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import tempfile

from guardrails_pack.bootstrap.application.inspection import (
    file_mode,
    pack_owned_hashes,
    package_names,
    read_text,
)
from guardrails_pack.bootstrap.application.ports import CommandRunner, ProjectionPayload
from guardrails_pack.bootstrap.application.transaction import Writer, transaction
from guardrails_pack.bootstrap.domain.errors import refuse
from guardrails_pack.bootstrap.domain.manifest import (
    MANIFEST_PATH,
    Manifest,
    digest,
    entries,
    ordering,
    parse,
    shim_state,
)
from guardrails_pack.bootstrap.domain.plan import Plan, build_plan, check_ownership, drifted

__all__ = ["UpdateRequest", "update_project"]

WORKSPACE_PREFIX = "pack-update-"
SOURCE_DIRECTORY = "src"
DRIFT_DIRECTORY = "pack/.drift"
SEPARATOR = "/"
ENCODING = "utf-8"
DESTINATION = "the destination"
INSTALLED_PACK = "the installed pack"
TOPLEVEL = ("git", "rev-parse", "--show-toplevel")
STATUS = ("git", "status", "--porcelain")


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateRequest:
    """One requested update: where it lands, and whether drift is overwritten."""

    destination: Path
    force: bool


def _package_of(root: Path, rule: str, where: str) -> str:
    """`U2`: the one directory under `src/`, which names the import package."""
    names = package_names(root)
    if len(names) != 1:
        raise refuse(
            rule,
            f"'{SOURCE_DIRECTORY}/' of {where} holds {len(names)} directories.",
            f"The pack-owned zone is '{SOURCE_DIRECTORY}/<package>/', so exactly one must exist.",
            f"Update the repository of one project, whose '{SOURCE_DIRECTORY}/' holds one package.",
        )
    return names[0]


def _manifest_of(root: Path, rule: str, where: str) -> Manifest:
    """`U1` and `U8`: the manifest of one tree, refused when it is absent."""
    text = read_text(root / MANIFEST_PATH)
    if text is None:
        raise refuse(
            rule,
            f"'{root}' holds no '{MANIFEST_PATH}'.",
            "That file records the bytes of every pack-owned file of a project.",
            "Update a project that this pack created.",
        )
    return parse(text, rule, where)


def _check_not_a_pack(destination: Path, package: str, capability: str) -> None:
    """`U7`: a tree that still holds this capability is a Root Pack, not a project."""
    if (destination / SOURCE_DIRECTORY / package / capability).is_dir():
        raise refuse(
            "U7",
            f"'{destination}' holds the '{capability}' capability, so it is a pack.",
            "A pack is the source of an update and can never be the destination of one.",
            "Update a project that this pack created.",
        )


def _check_worktree(runner: CommandRunner, destination: Path) -> None:
    """`U4`: the destination is its own git repository, and the worktree is clean."""
    if not runner.succeeds(TOPLEVEL, destination):
        raise refuse(
            "U4",
            f"'{destination}' is not a git repository.",
            "An update replaces whole files, and git is the only way back.",
            "Run 'git init' and commit the tree, then update it.",
        )
    toplevel = runner.read(TOPLEVEL, destination).strip()
    if Path(toplevel).resolve() != destination.resolve():
        raise refuse(
            "U4",
            f"'{destination}' is not the root of its git repository.",
            "An update replaces whole files, and git is the only way back.",
            f"Update '{toplevel}', which is that root.",
        )
    if runner.read(STATUS, destination).strip():
        raise refuse(
            "U4",
            f"The git worktree of '{destination}' is dirty.",
            "An update replaces whole files, and git is the only way back.",
            "Commit or stash your work, then update the tree.",
        )


def _check_installed(source: Path, manifest: Manifest, package: str) -> None:
    """`U8`: the installed pack's own manifest states the bytes it ships."""
    stale = drifted(entries(manifest, package), pack_owned_hashes(source, package))
    if stale:
        raise refuse(
            "U8",
            f"The installed pack records '{stale[0]}' with other bytes than it ships.",
            "A stale manifest makes an update read a changed file as an untouched one.",
            "Install a release whose manifest states its own tree.",
        )


def _check_version(recorded: Manifest, shipped: Manifest) -> None:
    """`U3`: a transition is forward-only, and it takes one jump."""
    if ordering(recorded.pack_version) > ordering(shipped.pack_version):
        newer = f"The project records {recorded.pack_version} and the pack is "
        raise refuse(
            "U3",
            f"{newer}{shipped.pack_version}, which is older.",
            "A transition is forward-only in one jump, so no migration code exists.",
            f"Install pack {recorded.pack_version} or later, then update again.",
        )


def _check_drift(drift: tuple[str, ...], destination: Path, *, force: bool) -> None:
    """`U5`: pack-owned drift refuses, because a silent overwrite loses work."""
    if drift and not force:
        raise refuse(
            "U5",
            f"'{drift[0]}' of '{destination}' left the bytes the project was born with.",
            "An update replaces whole pack-owned files, so it would discard that work.",
            f"Revert the {len(drift)} changed path(s), or pass --force to save and replace them.",
        )


def _origin_of(relative: str, package: str, source_package: str) -> str:
    """The same pack-owned location inside the installed pack, under its own package."""
    prefix = f"{SOURCE_DIRECTORY}{SEPARATOR}{package}{SEPARATOR}"
    if not relative.startswith(prefix):
        return relative
    return f"{SOURCE_DIRECTORY}{SEPARATOR}{source_package}{SEPARATOR}{relative[len(prefix) :]}"


def _apply(writer: Writer, plan: Plan, source: Path, packages: tuple[str, str]) -> None:
    """Write every added and replaced path, then remove every deleted path."""
    package, source_package = packages
    for relative in (*plan.added, *plan.replaced):
        origin = source / _origin_of(relative, package, source_package)
        writer.write(relative, origin.read_bytes(), file_mode(origin))
    for relative in plan.deleted:
        writer.remove(relative)


def _save_drift(writer: Writer, saved: Mapping[str, tuple[bytes, int]]) -> None:
    """Keep the replaced bytes of a forced update under `pack/.drift/<path>`."""
    for relative, (data, mode) in saved.items():
        writer.write(f"{DRIFT_DIRECTORY}{SEPARATOR}{relative}", data, mode)


def _digest_of(path: Path) -> str | None:
    """The sha256 of one file of the destination, or nothing when it is absent."""
    return digest(path.read_bytes()) if path.is_file() else None


def _shim_report(
    destination: Path, recorded: Manifest, shipped: Manifest
) -> tuple[dict[str, object], ...]:
    """One line per shim: its state, and whether this release ships other bytes."""
    return tuple(
        {
            "path": relative,
            "state": shim_state(
                recorded.shims.get(relative),
                _digest_of(destination / relative),
            ),
            "pack_changed": recorded.shims.get(relative) != shipped.shims.get(relative),
        }
        for relative in sorted({*recorded.shims, *shipped.shims})
    )


def update_project(
    payload: ProjectionPayload, runner: CommandRunner, request: UpdateRequest, capability: str
) -> dict[str, object]:
    """Replace the Pack-owned Surface of one project, and nothing else."""
    destination = request.destination
    recorded = _manifest_of(destination, "U1", DESTINATION)
    package = _package_of(destination, "U2", DESTINATION)
    _check_not_a_pack(destination, package, capability)
    _check_worktree(runner, destination)
    with tempfile.TemporaryDirectory(prefix=WORKSPACE_PREFIX) as workspace:
        source = Path(workspace)
        payload.unpack(source)
        source_package = _package_of(source, "U8", INSTALLED_PACK)
        shipped = _manifest_of(source, "U8", INSTALLED_PACK)
        _check_version(recorded, shipped)
        return _run(source, (package, source_package), (recorded, shipped), request)


def _run(
    source: Path,
    packages: tuple[str, str],
    manifests: tuple[Manifest, Manifest],
    request: UpdateRequest,
) -> dict[str, object]:
    """Steps 4 to 8, after every refusal that reads one whole record has passed.

    The three remaining refusals answer in this order: `U6` over the plan, `U8`
    over the installed pack, then `U5` over the drift. `U6` answers first
    because it is the promise the user cares about, and because a release that
    claims a path of theirs must name that path rather than its own record.
    `--force` passes `U5`, and it can never pass `U6` or `U8`.
    """
    destination = request.destination
    package, source_package = packages
    recorded, shipped = manifests
    present = pack_owned_hashes(destination, package)
    old = entries(recorded, package)
    plan = build_plan(old, entries(shipped, package), present)
    check_ownership(plan, package)
    _check_installed(source, shipped, source_package)
    drift = drifted(old, present)
    _check_drift(drift, destination, force=request.force)
    saved = {
        relative: ((destination / relative).read_bytes(), file_mode(destination / relative))
        for relative in plan.touched
        if relative in drift and (destination / relative).is_file()
    }
    manifest_text = read_text(source / MANIFEST_PATH) or ""
    written = _write(source, packages, plan, (saved, manifest_text), request)
    return _report(destination, manifests, plan, written, request)


def _write(
    source: Path,
    packages: tuple[str, str],
    plan: Plan,
    carried: tuple[Mapping[str, tuple[bytes, int]], str],
    request: UpdateRequest,
) -> int:
    """Step 7: one transaction, with `pack/manifest.json` written last."""
    saved, manifest_text = carried
    destination = request.destination
    current = read_text(destination / MANIFEST_PATH)
    stale = current != manifest_text
    if not plan.touched and not stale:
        return 0
    with transaction(destination) as writer:
        _apply(writer, plan, source, packages)
        _save_drift(writer, saved)
        if stale:
            origin = source / MANIFEST_PATH
            writer.write(MANIFEST_PATH, origin.read_bytes(), file_mode(origin))
    return len(plan.touched) + int(stale)


def _report(
    destination: Path,
    manifests: tuple[Manifest, Manifest],
    plan: Plan,
    written: int,
    request: UpdateRequest,
) -> dict[str, object]:
    """Step 8: the whole outcome, and the shim report that names no write."""
    recorded, shipped = manifests
    return {
        "directory": str(destination),
        "previous_version": recorded.pack_version,
        "pack_version": shipped.pack_version,
        "written": written,
        "added": list(plan.added),
        "replaced": list(plan.replaced),
        "deleted": list(plan.deleted),
        "forced": request.force,
        "shims": list(_shim_report(destination, recorded, shipped)),
    }
