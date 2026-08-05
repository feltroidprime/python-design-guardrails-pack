"""Read one tree the way the manifest states it: the package, and the hashes.

Both sides of a Pack Update are read through this module. The destination gives
the bytes the project has now, and the unpacked payload gives the bytes the
installed pack ships. One reader for both sides means refusal `U8` measures the
installed pack exactly as drift measures the destination.

The reader walks the two pack-owned zones only, and it drops every path that the
ownership predicate rejects and every path that is runtime output rather than
release content. `pack/manifest.json` is dropped as well: it is the one
pack-owned file that no manifest records.
"""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from guardrails_pack.bootstrap.domain.manifest import MANIFEST_PATH, digest
from guardrails_pack.bootstrap.domain.ownership import is_scanned, pack_owned

__all__ = ["file_mode", "pack_owned_hashes", "package_names", "read_text"]

SOURCE_DIRECTORY = "src"
PACK_DIRECTORY = "pack"
ENCODING = "utf-8"
PERMISSION_BITS = 0o777


def package_names(root: Path) -> tuple[str, ...]:
    """Every directory under `src/` that can be the import package of the tree."""
    source = root / SOURCE_DIRECTORY
    if not source.is_dir():
        return ()
    return tuple(
        sorted(
            entry.name
            for entry in source.iterdir()
            if entry.is_dir() and is_scanned(entry.name) and not entry.name.startswith(".")
        )
    )


def _zone_files(zone: Path) -> tuple[Path, ...]:
    if not zone.is_dir():
        return ()
    return tuple(sorted(path for path in zone.rglob("*") if path.is_file()))


def pack_owned_hashes(root: Path, package: str) -> Mapping[str, str]:
    """The sha256 of every pack-owned file of one tree, keyed by repository path."""
    zones = (root / PACK_DIRECTORY, root / SOURCE_DIRECTORY / package)
    found: dict[str, str] = {}
    for zone in zones:
        for path in _zone_files(zone):
            relative = path.relative_to(root).as_posix()
            if relative == MANIFEST_PATH or not is_scanned(relative):
                continue
            if pack_owned(relative, package):
                found[relative] = digest(path.read_bytes())
    return MappingProxyType(found)


def read_text(path: Path) -> str | None:
    """The text of one file, or nothing when that file is absent."""
    if not path.is_file():
        return None
    return path.read_text(encoding=ENCODING)


def file_mode(path: Path) -> int:
    """The permission bits of one file, which a whole-file replacement keeps."""
    return path.stat().st_mode & PERMISSION_BITS
