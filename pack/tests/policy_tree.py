"""Build the smallest tree the architecture policy accepts."""

from pathlib import Path

from scripts.architecture_policy import PACK_DIRECTORY, POLICY_RELATIVE, SOURCE_DIRECTORY

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PACKAGE = "pkg"
# The suppression marker without its number. A test builds a planted marker from
# this prefix rather than writing one whole, because `DOC002` searches every
# Python file of the tree for a whole marker and would then read a fixture as a
# real claim on an ADR that does not exist.
EXCEPTION_MARKER = "ARCH-EXCEPTION: ADR-"


def write_policy_tree(root: Path, package: str = FIXTURE_PACKAGE) -> Path:
    """Build the smallest tree `load_policy` accepts: the pack policy and one package.

    The policy names no package, so the package comes from the one directory
    under `src/`. Every test tree therefore states its package exactly once.
    """
    (root / POLICY_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
    _ = (root / POLICY_RELATIVE).write_text(
        (REPOSITORY_ROOT / PACK_DIRECTORY / "architecture.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / SOURCE_DIRECTORY / package).mkdir(parents=True, exist_ok=True)
    return root
