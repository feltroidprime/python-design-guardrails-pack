#!/usr/bin/env python3
"""Prove that `pack/manifest.json` states the current pack-owned bytes.

`pack/manifest.json` records the sha256 of every pack-owned file. A Pack Update
compares that record against the destination to find local drift, so a stale
manifest makes the update believe a changed file is untouched. Refusal `U8` of
#85 catches the same defect from the outside, at update time. This hook catches
it from the inside, at commit time.

The check recomputes each hash with `hashlib`, reads and writes the record with
`json`, and walks the tree with `pathlib`. It runs no other tool. Ownership
comes from the one predicate in `scripts.ownership`, never from a second copy of
the rule and never from the manifest's own path list.

The manifest holds three lists, so it carries no identity token (#85 section
3.4):

* `root` — literal repository paths under `pack/`, `pack/manifest.json` apart,
  because that one file cannot hash itself;
* `package` — paths relative to `src/<pkg>/`, whose name the reader derives;
* `shims` — the as-shipped hash of each user-owned entry point, which an update
  reads to tell a customised shim from an untouched one, and never writes.

Run `uv run python -m scripts.manifest_guard --write` after you change a
pack-owned file.
"""

import hashlib
import json
from pathlib import Path
import sys
import tomllib
from typing import TypedDict, cast

from scripts.identity import DiscoveryError, discover_package
from scripts.ownership import pack_owned

MANIFEST = Path("pack/manifest.json")
PACK_DIRECTORY = Path("pack")
SOURCE_DIRECTORY = Path("src")
PROJECT_FILE = Path("pyproject.toml")
SHIMS = (
    Path("justfile"),
    Path(".python-version"),
    Path("pyrightconfig.json"),
    Path(".github/workflows/quality.yml"),
)
# Runtime output that lives inside a pack-owned zone and belongs to no release:
# bytecode caches, the cache directory each tool writes beside its own config,
# the forced-update backups, and the staged projection blob. A cache path in the
# record makes the hook red on the next clean checkout, and it makes every later
# Pack Update refuse a project that never drifted.
IGNORED_NAMES = frozenset(
    {
        ".basedpyright",
        ".drift",
        ".hypothesis",
        ".import_linter_cache",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "_pack.tar",
    }
)
IGNORED_SUFFIXES = (".pyc", ".pyo")
REPAIR_COMMAND = "uv run python -m scripts.manifest_guard --write"
USAGE = "Usage: python -m scripts.manifest_guard [--write]"


class Manifest(TypedDict):
    """The record that a Pack Update reads to find local drift."""

    pack_version: str
    root: dict[str, str]
    package: dict[str, str]
    shims: dict[str, str]


class ManifestError(RuntimeError):
    """Raised when the manifest cannot be read or rebuilt."""


def repository_root() -> Path:
    """The repository root, resolved from this script location."""
    return Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    """The sha256 of one file, in lowercase hexadecimal."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ignored(relative: Path) -> bool:
    if relative.suffix in IGNORED_SUFFIXES:
        return True
    return any(part in IGNORED_NAMES for part in relative.parts)


def _files_under(root: Path, directory: Path) -> tuple[Path, ...]:
    start = root / directory
    if not start.is_dir():
        return ()
    return tuple(
        sorted(
            path.relative_to(root)
            for path in start.rglob("*")
            if path.is_file() and not _ignored(path.relative_to(root))
        )
    )


def root_hashes(root: Path) -> dict[str, str]:
    """The sha256 of every pack-owned file under `pack/`, this manifest apart."""
    return {
        relative.as_posix(): digest(root / relative)
        for relative in _files_under(root, PACK_DIRECTORY)
        if relative != MANIFEST
    }


def package_hashes(root: Path, package: str) -> dict[str, str]:
    """The sha256 of every pack-owned file inside `src/<pkg>/`, keyed inside it."""
    package_root = SOURCE_DIRECTORY / package
    return {
        relative.relative_to(package_root).as_posix(): digest(root / relative)
        for relative in _files_under(root, package_root)
        if pack_owned(relative.as_posix(), package)
    }


def shim_hashes(root: Path) -> dict[str, str]:
    """The as-shipped sha256 of each user-owned entry point that is present."""
    return {
        relative.as_posix(): digest(root / relative)
        for relative in SHIMS
        if (root / relative).is_file()
    }


def pack_version(root: Path) -> str:
    """The version of the pack, read from the one `pyproject.toml`."""
    try:
        project = cast(
            "dict[str, object]",
            tomllib.loads((root / PROJECT_FILE).read_text(encoding="utf-8")),
        )
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ManifestError(f"{PROJECT_FILE} could not be read: {error}") from error
    section = project.get("project")
    if not isinstance(section, dict):
        raise ManifestError(f"{PROJECT_FILE} declares no [project] table.")
    version = cast("dict[str, object]", section).get("version")
    if not isinstance(version, str):
        raise ManifestError(f"{PROJECT_FILE} declares no [project] version.")
    return version


def build(root: Path) -> Manifest:
    """The manifest that states the current tree."""
    package = discover_package(root)
    return Manifest(
        pack_version=pack_version(root),
        root=root_hashes(root),
        package=package_hashes(root, package),
        shims=shim_hashes(root),
    )


def _section(manifest: dict[str, object], name: str) -> dict[str, str]:
    section = manifest.get(name)
    if not isinstance(section, dict):
        raise ManifestError(f"{MANIFEST} has no '{name}' list.")
    entries = cast("dict[object, object]", section)
    return {str(key): str(value) for key, value in entries.items()}


def read(root: Path) -> dict[str, object]:
    """The manifest as it is recorded on disk."""
    path = root / MANIFEST
    if not path.is_file():
        raise ManifestError(f"{MANIFEST} does not exist. Run `{REPAIR_COMMAND}`.")
    try:
        recorded = cast("object", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"{MANIFEST} could not be read: {error}") from error
    if not isinstance(recorded, dict):
        raise ManifestError(f"{MANIFEST} is not a JSON object.")
    return cast("dict[str, object]", recorded)


def differences(recorded: dict[str, str], current: dict[str, str], name: str) -> list[str]:
    """One line for each path whose record disagrees with the tree."""
    absent = sorted(recorded.keys() - current.keys())
    unrecorded = sorted(current.keys() - recorded.keys())
    changed = sorted(
        path for path in recorded.keys() & current.keys() if recorded[path] != current[path]
    )
    return [
        *(f"{name}: {path} is recorded but absent" for path in absent),
        *(f"{name}: {path} is present but unrecorded" for path in unrecorded),
        *(f"{name}: {path} changed since the manifest was written" for path in changed),
    ]


def verify(root: Path) -> list[str]:
    """Every disagreement between the manifest and the tree."""
    recorded = read(root)
    current = build(root)
    return [
        *differences(_section(recorded, "root"), current["root"], "root"),
        *differences(_section(recorded, "package"), current["package"], "package"),
        *differences(_section(recorded, "shims"), current["shims"], "shims"),
    ]


def write(root: Path) -> None:
    """Record the current tree in the manifest."""
    text = json.dumps(build(root), indent=2, sort_keys=True) + "\n"
    _ = (root / MANIFEST).write_text(text, encoding="utf-8")
    print(f"Wrote {MANIFEST}.")


def main(argv: list[str]) -> int:
    root = repository_root()
    try:
        if argv == ["--write"]:
            write(root)
            return 0
        if argv:
            print(USAGE, file=sys.stderr)
            return 2
        report = verify(root)
    except (DiscoveryError, ManifestError, OSError) as error:
        print(f"Manifest check could not run: {error}", file=sys.stderr)
        return 2
    if report:
        for line in report:
            print(line, file=sys.stderr)
        print(f"\n{len(report)} manifest disagreement(s). Run `{REPAIR_COMMAND}`.", file=sys.stderr)
        return 1
    print("Manifest matches the pack-owned tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
