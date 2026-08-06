"""Project this pack once into one new repository, and release the pack itself.

The pack-owned router reads this module and derives the command line from it, so
the command is always three tokens: `<project> <capability> <function>`. Every
public function below is one subcommand, and the parameters below are its
positionals and options.

```
pyrepo bootstrap init    <name> [directory] [--package NAME] [--github] [--public]
pyrepo bootstrap update  [directory] [--force]
pyrepo bootstrap release [--directory DIRECTORY]
```

`init` never touches the network. `--github` is the one network step, and
`--public` selects the visibility of the repository it creates. No boolean
option defaults to `True` (clause A3 of #85), so the default run is offline and
the new repository stays private.

`update` never touches the network either, and it never runs the gate.
"""

from pathlib import Path

from guardrails_pack.bootstrap.adapters.outbound.commands import LocalCommands
from guardrails_pack.bootstrap.adapters.outbound.payload import (
    checkout_root,
    locate_payload,
    package_root,
)
from guardrails_pack.bootstrap.application.creation import (
    Request,
    create_project,
    requested_identity,
)
from guardrails_pack.bootstrap.application.projection import CAPABILITY
from guardrails_pack.bootstrap.application.release import WHEEL_DIRECTORY, stage_and_build
from guardrails_pack.bootstrap.application.update import UpdateRequest, update_project

__all__ = ["init", "release", "update"]


def init(
    name: str,
    directory: Path | None = None,
    /,
    *,
    package: str = "",
    github: bool = False,
    public: bool = False,
) -> dict[str, object]:
    """Create one new repository from this pack.

    The projection copies the pack tree, swaps the two identity tokens, overlays
    the starting files, and deletes this capability. It then runs
    `git init`, `just setup`, the first commit, and `prek install`.

    The destination must not exist; the projection creates it. Every refusal
    happens before the destination is written, and it ends with the same
    promise: nothing was written.
    """
    project = requested_identity(name, package)
    chosen = Path(project.project_name) if directory is None else directory
    request = Request(
        project=project,
        destination=Path.cwd() / chosen.expanduser(),
        github=github,
        public=public,
    )
    return create_project(locate_payload(), LocalCommands(), request)


def update(directory: Path | None = None, /, *, force: bool = False) -> dict[str, object]:
    """Carry this pack's whole Pack-owned Surface into one existing project.

    The update replaces pack-owned files only, and it never writes a file you
    own. It refuses a dirty worktree, because git is the only way back, and it
    refuses a pack-owned file that left the bytes the project was born with.
    `--force` replaces such a file and saves the old bytes under
    `pack/.drift/<path>`.

    The update carries the current tool policy and never runs the gate. A gate
    that turns red on your own code after an update is the signal to adapt that
    code.
    """
    chosen = Path() if directory is None else directory
    request = UpdateRequest(destination=Path.cwd() / chosen.expanduser(), force=force)
    return update_project(locate_payload(), LocalCommands(), request, CAPABILITY)


def release(*, directory: Path | None = None) -> dict[str, object]:
    """Build one wheel of this pack, with the projection payload inside it.

    The payload is one archive of `HEAD`, so a release must commit first: work
    that is not committed is absent from the wheel. The archive is staged inside
    the package, the wheel is built, and the archive is deleted again.
    """
    wheels = Path.cwd() / Path(directory or WHEEL_DIRECTORY).expanduser()
    return stage_and_build(LocalCommands(), checkout_root(), package_root().name, wheels)
