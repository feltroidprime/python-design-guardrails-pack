"""The packaging shape: one project file that a Terminal Project can carry.

`pyproject.toml` serves the Root Pack and every Terminal Project. The backend is
`uv_build`, which includes what sits under the module root, so inclusion is by
presence and the file needs no include table. The projection payload is one
archive of the last commit, staged inside the package at build time and never
committed.

The earlier `hatchling` shape failed here. Its `force-include` table sat inside
the file that projection rewrites, so the table could not erase itself, and
every Terminal Project shipped a copy of the pack. These tests state the four
facts that measurement killed that shape on, and they prepare assertions `TER-1`
to `TER-4` of #81, which the acceptance suite proves from the installed console
script.
"""

from pathlib import Path
import re
import tomllib
from typing import cast

from scripts.identity import discover_package

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_FILE = Path("pyproject.toml")
GATE = Path("pack/configs/prek.toml")
BUILD_REQUIREMENT = "uv_build==0.12.0"
BUILD_BACKEND = "uv_build"
ENTRY_POINT = "cli:main"
# The name of the staged archive, written in two parts. `pack/` reaches a
# Terminal Project byte for byte, and assertion TER-6 of #81 forbids the whole
# name in any file of that project.
BLOB_NAME = "_pack" + ".tar"
# The two strings that assertion TER-1 of #81 counts in a Terminal Project's
# `pyproject.toml`. The count must be zero.
PACK_ONLY_MARKERS = ("force-include", "_pack")
# The neutral identity is derived, never written. Upper-casing this tree's own
# two values gives a pair that rule R2 of the projection can never admit, so
# this pack-owned file holds no identity of its own and cannot collide with the
# identity of the project that carries it.


def load(path: Path) -> dict[str, object]:
    return cast("dict[str, object]", tomllib.loads(path.read_text(encoding="utf-8")))


def table(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def text(value: object) -> str:
    assert isinstance(value, str)
    return value


def project_metadata() -> dict[str, object]:
    return load(REPOSITORY_ROOT / PROJECT_FILE)


def identity() -> tuple[str, str]:
    """The distribution name and the import package name of this tree."""
    project = project_metadata()
    return (
        text(table(project["project"])["name"]),
        text(table(table(table(project["tool"])["uv"])["build-backend"])["module-name"]),
    )


def projected_project_text() -> str:
    """The project file as a Terminal Project carries it, after the token swap."""
    distribution, package = identity()
    raw = (REPOSITORY_ROOT / PROJECT_FILE).read_text(encoding="utf-8")
    return raw.replace(package, package.upper()).replace(distribution, distribution.upper())


def test_the_build_backend_is_uv_build_at_the_pinned_version() -> None:
    build_system = table(project_metadata()["build-system"])

    assert build_system["requires"] == [BUILD_REQUIREMENT]
    assert build_system["build-backend"] == BUILD_BACKEND


def test_the_backend_names_the_one_import_package_of_the_tree() -> None:
    _, package = identity()

    assert package == discover_package(REPOSITORY_ROOT)


def test_the_console_script_names_the_distribution_and_the_user_owned_shim() -> None:
    distribution, package = identity()
    scripts = table(table(project_metadata()["project"])["scripts"])

    assert list(scripts) == [distribution]
    assert scripts[distribution] == f"{package}.{ENTRY_POINT}"


def test_the_projected_project_file_holds_no_pack_only_packaging_line() -> None:
    projected = projected_project_text()

    found = [marker for marker in PACK_ONLY_MARKERS if marker in projected]

    assert found == []


def test_the_gate_ignores_the_staged_archive() -> None:
    exclude = text(load(REPOSITORY_ROOT / GATE)["exclude"])
    _, package = identity()

    assert re.search(exclude, f"src/{package}/{BLOB_NAME}") is not None
