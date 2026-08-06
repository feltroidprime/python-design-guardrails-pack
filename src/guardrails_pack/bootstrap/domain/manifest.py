"""The record a Pack Update reads on the destination and the installed pack: `pack/manifest.json`.

A release generates the manifest at build time, ships it inside the projection
payload, and the projection projects it verbatim. It holds three hash lists, so
it carries no identity token and needs no placeholder markup:

* `root` — literal repository paths under `pack/`. `pack/manifest.json` is
  excluded, because it is the one pack-owned file that cannot hash itself;
* `package` — paths relative to `src/<pkg>/`, whose name the reader derives from
  the destination;
* `shims` — the as-shipped hash of each user-owned entry point. An update reads
  those hashes to tell a customised shim from an untouched one, and it never
  writes a shim.

A version transition is forward-only and takes one jump. An equal version is a
no-op, and a lower version is refused. No migration code ever ships, so this
module reads one shape only and states no history.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import cast

from guardrails_pack.bootstrap.domain.errors import refuse

__all__ = [
    "MANIFEST_PATH",
    "Manifest",
    "digest",
    "entries",
    "ordering",
    "parse",
    "shim_state",
]

MANIFEST_PATH = "pack/manifest.json"
SOURCE_DIRECTORY = "src"
SEPARATOR = "/"
VERSION_SEPARATOR = "."
VERSION_FIELD = "pack_version"
SECTIONS = ("root", "package", "shims")
ENCODING = "utf-8"

# The three answers of the shim report. `CUSTOMISED` is the one that matters: a
# shim whose bytes left the as-shipped hash is the owner's file now.
CUSTOMISED = "customised"
UNTOUCHED = "untouched"
ABSENT = "absent"


@dataclass(frozen=True, slots=True, kw_only=True)
class Manifest:
    """One `pack/manifest.json`, of one pack or of one project."""

    pack_version: str
    root: Mapping[str, str]
    package: Mapping[str, str]
    shims: Mapping[str, str]


def digest(data: bytes) -> str:
    """The sha256 of one file, in lowercase hexadecimal."""
    return hashlib.sha256(data).hexdigest()


def ordering(version: str) -> tuple[int, ...]:
    """The comparable release numbers of one version, longest prefix that is numeric."""
    numbers: list[int] = []
    for segment in version.split(VERSION_SEPARATOR):
        digits = ""
        for character in segment:
            if not character.isdigit():
                break
            digits += character
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers)


def _hashes(recorded: object, name: str, rule: str, where: str) -> Mapping[str, str]:
    if not isinstance(recorded, dict):
        raise refuse(
            rule,
            f"The manifest of {where} states no '{name}' list.",
            "An update reads three hash lists from that file and compares them.",
            "Update from a release that ships a whole manifest.",
        )
    listed: dict[str, str] = {}
    for key, value in cast("dict[object, object]", recorded).items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise refuse(
                rule,
                f"The '{name}' list of {where} holds an entry that is not text.",
                "Each entry states one path and the sha256 of that path.",
                "Update from a release that ships a whole manifest.",
            )
        listed[key] = value
    return MappingProxyType(listed)


def parse(text: str, rule: str, where: str) -> Manifest:
    """Read one manifest. Refuse *rule* when the text states no whole record."""
    try:
        recorded = cast("object", json.loads(text))
    except json.JSONDecodeError as error:
        raise refuse(
            rule,
            f"The manifest of {where} is not readable JSON: {error}.",
            "An update reads the recorded bytes of every pack-owned file from it.",
            "Restore that file from the release the project was born from.",
        ) from error
    if not isinstance(recorded, dict):
        raise refuse(
            rule,
            f"The manifest of {where} is not a JSON object.",
            "An update reads a version and three hash lists from it.",
            "Restore that file from the release the project was born from.",
        )
    fields: dict[str, object] = {
        str(key): value for key, value in cast("dict[object, object]", recorded).items()
    }
    version = fields.get(VERSION_FIELD)
    if not isinstance(version, str) or not ordering(version):
        raise refuse(
            rule,
            f"The manifest of {where} states no readable '{VERSION_FIELD}'.",
            "The version decides whether the transition is forward, equal, or backward.",
            "Restore that file from the release the project was born from.",
        )
    root, package, shims = (_hashes(fields.get(name), name, rule, where) for name in SECTIONS)
    return Manifest(pack_version=version, root=root, package=package, shims=shims)


def entries(manifest: Manifest, package: str) -> Mapping[str, str]:
    """Every pack-owned path of one manifest, keyed by its repository path."""
    prefix = f"{SOURCE_DIRECTORY}{SEPARATOR}{package}{SEPARATOR}"
    located = {
        **dict(manifest.root),
        **{f"{prefix}{relative}": recorded for relative, recorded in manifest.package.items()},
    }
    return MappingProxyType(located)


def shim_state(recorded: str | None, present: str | None) -> str:
    """The report answer for one shim: absent, customised, or untouched."""
    if present is None:
        return ABSENT
    if recorded is None or recorded != present:
        return CUSTOMISED
    return UNTOUCHED
