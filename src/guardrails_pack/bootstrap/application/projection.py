"""Terminal Projection: four file operations, and the three checks that follow.

```
1. copy the Root Pack tree, excluding the staged projection blob
2. swap the two identity tokens in every file, and rename every path
   component equal to a pack token
3. overlay the starting files of initial/ at their renamed paths
4. delete the capability directory
```

No template engine runs, and no file receives an interior edit beyond the token
swap. The whole tree is built in a temporary directory, and
`R7` to `R9` read it back before the caller moves it into place.

The capability directory name is read from this module's own name, so no
literal of it appears here and the same code holds for a capability of any
name.
"""

from pathlib import Path
import shutil

from guardrails_pack.bootstrap.application.ports import ProjectionPayload
from guardrails_pack.bootstrap.domain.errors import refuse
from guardrails_pack.bootstrap.domain.identity import Identity, substitutions
from guardrails_pack.bootstrap.domain.projection import (
    found_tokens,
    rename_components,
    swap_tokens,
)

__all__ = ["CAPABILITY", "build_project"]

# `guardrails_pack.<capability>.application.projection` -> `<capability>`.
CAPABILITY = __name__.split(".")[1]
STARTING_FILES = "initial"
SOURCE_DIRECTORY = "src"
STAGING_DIRECTORY = "staging"
BUILD_DIRECTORY = "build"
PERMISSION_BITS = 0o777


def _write_link(source: Path, target: Path, pairs: tuple[tuple[str, str], ...]) -> None:
    """Recreate one symbolic link, with both tokens swapped in its own target."""
    literal = str(source.readlink())
    target.symlink_to(rename_components(swap_tokens(literal.encode(), pairs).decode(), pairs))


def _write_file(source: Path, target: Path, pairs: tuple[tuple[str, str], ...]) -> None:
    """Copy one file with both tokens swapped, and keep its permission bits."""
    _ = target.write_bytes(swap_tokens(source.read_bytes(), pairs))
    target.chmod(source.stat().st_mode & PERMISSION_BITS)


def _rewrite(staging: Path, built: Path, pairs: tuple[tuple[str, str], ...]) -> None:
    """Steps 1 and 2: copy every entry to its renamed path, with tokens swapped."""
    for source in sorted(staging.rglob("*")):
        relative = rename_components(source.relative_to(staging).as_posix(), pairs)
        target = built / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            _write_link(source, target, pairs)
        elif source.is_dir():
            target.mkdir(exist_ok=True)
        else:
            _write_file(source, target, pairs)


def _starting_root(built: Path, project: Identity) -> Path:
    """Where the starting files sit after the rename of step 2."""
    return built / SOURCE_DIRECTORY / project.package / CAPABILITY / STARTING_FILES


def _overlay(built: Path, project: Identity) -> dict[str, bytes]:
    """Step 3: replace each shadowed file, and refuse `R9` when one shadows nothing."""
    root = _starting_root(built, project)
    if not root.is_dir():
        raise refuse(
            "R9",
            f"The payload holds no '{STARTING_FILES}/' directory.",
            "A new project starts from the files that directory carries.",
            "Commit the whole capability, then build the payload again.",
        )
    landed: dict[str, bytes] = {}
    for source in sorted(root.rglob("*")):
        if source.is_dir():
            continue
        relative = source.relative_to(root).as_posix()
        target = built / relative
        if not target.is_file():
            raise refuse(
                "R9",
                f"The starting file '{relative}' shadows no file of the pack.",
                "The overlay can only replace a file, never add one.",
                f"Delete it from '{STARTING_FILES}/', or add the file it must replace.",
            )
        data = source.read_bytes()
        _ = target.write_bytes(data)
        landed[relative] = data
    return landed


def _delete_capability(built: Path, project: Identity) -> None:
    """Step 4: delete the capability directory, and with it every trace of it."""
    shutil.rmtree(built / SOURCE_DIRECTORY / project.package / CAPABILITY)


def _check_tokens(built: Path, pack: Identity) -> None:
    """`R7`: no file of the built tree still holds a pack token."""
    for candidate in sorted(built.rglob("*")):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        tokens = found_tokens(candidate.read_bytes(), pack)
        if tokens:
            relative = candidate.relative_to(built).as_posix()
            raise refuse(
                "R7",
                f"'{relative}' still holds the pack token '{tokens[0]}'.",
                "A Terminal Project must carry your identity only, and never the pack name.",
                "Choose a name that holds no pack token, or report a defect of the pack.",
            )


def _check_capability(built: Path) -> None:
    """`R8`: no capability directory of the pack survives anywhere."""
    for candidate in sorted(built.rglob(CAPABILITY)):
        if candidate.is_dir():
            relative = candidate.relative_to(built).as_posix()
            raise refuse(
                "R8",
                f"The directory '{relative}' survived the projection.",
                "A Terminal Project cannot hold the capability that creates a repository.",
                "Report this as a defect of the pack.",
            )


def _check_landed(built: Path, landed: dict[str, bytes]) -> None:
    """`R9`: every starting file is still in place after step 4."""
    for relative, data in landed.items():
        target = built / relative
        if not target.is_file() or target.read_bytes() != data:
            raise refuse(
                "R9",
                f"The starting file '{relative}' did not land.",
                "A new project starts from the starting files of the pack.",
                "Report this as a defect of the pack.",
            )


def build_project(
    payload: ProjectionPayload, workspace: Path, pack: Identity, project: Identity
) -> Path:
    """Run the four steps inside *workspace*, then `R7` to `R9`. Return the tree."""
    staging = workspace / STAGING_DIRECTORY
    built = workspace / BUILD_DIRECTORY
    payload.unpack(staging)
    pairs = substitutions(pack, project)
    _rewrite(staging, built, pairs)
    landed = _overlay(built, project)
    _delete_capability(built, project)
    _check_tokens(built, pack)
    _check_capability(built)
    _check_landed(built, landed)
    return built
