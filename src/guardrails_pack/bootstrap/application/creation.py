"""One `init`: refuse, build in a temporary directory, move, then set up.

The order is the order of #85 section 3.3.

```
1. run R1, R2, R3, R5 and R6, which read the request and the filesystem
2. read the identity of the pack from the projection source
3. run R4, the one rule that compares the request against that identity
4. build the whole project in a temporary directory
5. run R7 to R9
6. move the tree into place as one operation
7. git init, just setup, and the first commit
8. prek install, which records the pack-owned config path in the git hook
9. with --github, gh repo create and push
```

Steps 1 to 6 never touch the network, and a failure in any of them leaves the
destination absent. Step 9 is the one network step, and it is opt-in. No boolean
flag defaults to `True` (clause A3 of #85), so `init` is testable offline and a
new repository stays private until its owner says otherwise.

Step 2 sits between two groups of refusals rather than before all of them, and
that placement is the whole point. Reading the projection source can fail: an
interrupted `release` leaves a staged archive that is not a readable archive at
all. A refusal that reads the pack before it needs to would then answer that
caller with an unexpected failure instead of with `R2` or `R5`. Assertion
`TER-4` of #81 states the rule that forbids it, so every refusal here reads the
narrowest fact that can answer it.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
import tempfile

from guardrails_pack.bootstrap.application.pipeline import prepare_repository, publish
from guardrails_pack.bootstrap.application.ports import CommandRunner, ProjectionPayload
from guardrails_pack.bootstrap.application.projection import build_project
from guardrails_pack.bootstrap.domain.errors import refuse
from guardrails_pack.bootstrap.domain.identity import (
    Identity,
    check_request,
    check_tokens,
    derive_package,
)

__all__ = ["Request", "create_project", "requested_identity"]

WORKSPACE_PREFIX = ".projection-"


@dataclass(frozen=True, slots=True, kw_only=True)
class Request:
    """One requested project: its identity, its destination, and its publication."""

    project: Identity
    destination: Path
    github: bool
    public: bool


def requested_identity(name: str, package: str) -> Identity:
    """The identity of the request, with the package derived when it is absent."""
    return Identity(project_name=name, package=package or derive_package(name))


def _check_destination(destination: Path) -> Path:
    """`R5` and `R6`: the destination is absent, and its nearest parent is writable."""
    if destination.exists() or destination.is_symlink():
        raise refuse(
            "R5",
            f"'{destination}' already exists.",
            "The projection writes a whole tree, so it never merges into an existing one.",
            "Give a location that does not exist, or move the existing one away.",
        )
    parents = (destination.parent, *destination.parent.parents)
    anchor = next((parent for parent in parents if parent.exists()), None)
    if anchor is None or not anchor.is_dir() or not os.access(anchor, os.W_OK | os.X_OK):
        raise refuse(
            "R6",
            f"'{destination}' cannot be created.",
            "The projection writes the whole tree at once, so it checks the parent first.",
            "Give a location below a directory you can write.",
        )
    return anchor


def _land(payload: ProjectionPayload, request: Request, pack: Identity, anchor: Path) -> None:
    """Build the tree beside the destination, then move it in as one operation."""
    workspace = Path(tempfile.mkdtemp(dir=anchor, prefix=WORKSPACE_PREFIX))
    try:
        built = build_project(payload, workspace, pack, request.project)
        request.destination.parent.mkdir(parents=True, exist_ok=True)
        _ = built.rename(request.destination)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def create_project(
    payload: ProjectionPayload, runner: CommandRunner, request: Request
) -> dict[str, object]:
    """Project the pack once into one new Terminal Project, then set it up."""
    check_request(request.project, frozenset(sys.stdlib_module_names))
    anchor = _check_destination(request.destination)
    pack = payload.identity()
    check_tokens(request.project, pack)
    _land(payload, request, pack, anchor)
    prepare_repository(runner, request.destination, request.project)
    if request.github:
        publish(runner, request.destination, request.project, public=request.public)
    return {
        "project_name": request.project.project_name,
        "package": request.project.package,
        "directory": str(request.destination),
        "published": request.github,
    }
