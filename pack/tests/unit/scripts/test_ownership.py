"""The ownership predicate, and the surface it answers in this repository.

Two zones exist and one predicate states them. These tests do two things. They
check the predicate against named paths, and they check it against the real
tracked tree, so a new path cannot quietly change the zone that owns it.
"""

from pathlib import Path
import subprocess

from scripts.architecture_policy import derive_package
from scripts.ownership import pack_owned

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
TRACKED_NAMES_COMMAND = ("git", "ls-files", "-z", "--cached", "--exclude-standard")
# A stand-in package name. Rule R2 of the projection admits a lower-case name
# only, so no real project can hold this one, and this pack-owned file cannot
# collide with the identity of the project that carries it.
PACKAGE = "PLACEHOLDER_PACKAGE"
PACK_OWNED_NAMES = (
    "pack",
    "pack/.gitignore",
    "pack/manifest.json",
    "pack/configs/ruff.toml",
    "pack/scripts/ownership.py",
    f"src/{PACKAGE}/py.typed",
    f"src/{PACKAGE}/__init__.py",
    f"src/{PACKAGE}/_foundation/router.py",
)
USER_OWNED_NAMES = (
    "justfile",
    "pyproject.toml",
    "pyrightconfig.json",
    ".python-version",
    ".github/workflows/quality.yml",
    "docs/adr/0001-a-decision.md",
    "tests/test_billing.py",
    "packages/report.py",
    "src",
    f"src/{PACKAGE}",
    f"src/{PACKAGE}/cli.py",
    f"src/{PACKAGE}/composition.py",
    f"src/{PACKAGE}/billing/api.py",
    "src/OTHER_PACKAGE/_foundation/router.py",
)


def tracked_names(root: Path) -> tuple[str, ...]:
    completed = subprocess.run(  # noqa: S603  # ARCH-EXCEPTION: ADR-0007
        TRACKED_NAMES_COMMAND,
        cwd=root,
        capture_output=True,
        check=True,
    )
    return tuple(raw.decode() for raw in completed.stdout.split(b"\0") if raw)


def expected_pack_owned(names: tuple[str, ...], package: str) -> tuple[str, ...]:
    """The Pack-owned Surface, written a second time as a text rule."""
    return tuple(
        name
        for name in names
        if name.startswith(("pack/", f"src/{package}/_")) or name == f"src/{package}/py.typed"
    )


def test_the_pack_directory_and_the_pack_owned_names_are_pack_owned() -> None:
    owned = tuple(name for name in PACK_OWNED_NAMES if pack_owned(name, PACKAGE))

    assert owned == PACK_OWNED_NAMES


def test_every_other_path_is_user_owned() -> None:
    owned = tuple(name for name in USER_OWNED_NAMES if pack_owned(name, PACKAGE))

    assert owned == ()


def test_the_predicate_reads_the_package_name_it_is_given() -> None:
    assert pack_owned("src/first/_foundation/router.py", "first") is True
    assert pack_owned("src/first/_foundation/router.py", "second") is False


def test_this_repository_holds_exactly_two_ownership_zones() -> None:
    package = derive_package(REPOSITORY_ROOT / "src")
    names = tracked_names(REPOSITORY_ROOT)
    owned = tuple(name for name in names if pack_owned(name, package))

    assert names, "the repository must track at least one file"
    assert owned == expected_pack_owned(names, package)


def test_every_tracked_path_under_the_pack_directory_is_pack_owned() -> None:
    package = derive_package(REPOSITORY_ROOT / "src")
    under_pack = tuple(name for name in tracked_names(REPOSITORY_ROOT) if name.startswith("pack/"))

    assert under_pack
    assert all(pack_owned(name, package) for name in under_pack)
