"""The release step: stage the payload, build the wheel, delete the payload.

Three commands, in this order:

```
git archive HEAD -o src/<pkg>/_pack.tar
uv build --wheel
rm src/<pkg>/_pack.tar
```

The step belongs to this capability and never to a `just` recipe. A recipe in
`pack/justfile` reaches every Terminal Project, and a Terminal Project must
carry no pack-only instruction. The root `justfile` therefore stays
byte-identical downstream, and the step disappears with the capability.

The archive holds `HEAD`, so a release must commit first. Uncommitted work is
absent from the wheel. The delete runs even when the build fails, because an
archive left in the tree is a defect the gate is told to ignore.
"""

from pathlib import Path

from guardrails_pack.bootstrap.application.ports import CommandRunner
from guardrails_pack.bootstrap.domain.projection import BLOB_NAME, SOURCE_DIRECTORY

__all__ = ["stage_and_build"]

WHEEL_DIRECTORY = "dist"


def stage_and_build(
    runner: CommandRunner, root: Path, package: str, directory: Path
) -> dict[str, object]:
    """Stage the payload of one commit, build one wheel, and clear the tree again."""
    blob = root / SOURCE_DIRECTORY / package / BLOB_NAME
    blob.parent.mkdir(parents=True, exist_ok=True)
    runner.run(("git", "archive", "HEAD", "-o", str(blob)), root)
    try:
        runner.run(("uv", "build", "--wheel", "-o", str(directory)), root)
    finally:
        blob.unlink(missing_ok=True)
    return {"payload": str(blob), "wheels": str(directory), "staged": False}
