"""Code A, A2, B, C, D and E of #81, as the six supporting checks of the suite.

Each function here answers one question and states no assertion. The test module
that reads the answer holds the assertion, so an assertion always names the
assertion id it carries.

Two adaptations of Code A are worth stating, because both are forced by the tree
rather than chosen. The projection payload is one archive of `HEAD`, so the file
set of the Root Pack is what git tracks, not what the working directory holds; a
virtual environment and every tool cache would otherwise enter the comparison.
The projected tree is read the same way, through the `.gitignore` it carried, so
both sides of the comparison hold release content and nothing else.

The ownership predicate of Code E is restated here rather than imported. A
measurement that reads the code it measures proves nothing.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess
import tarfile
import tomllib
from typing import cast

from guardrails_pack.bootstrap.tests.acceptance.harness import (
    GATE_CONFIG,
    present_files,
    tracked_files,
)

__all__ = [
    "CAPABILITY",
    "OFFLINE_PROBE",
    "PROBE_MODULE",
    "SOCKET_FAILURE",
    "Parity",
    "Tokens",
    "archive_digests",
    "commit_digests",
    "compare",
    "gate_hook_ids",
    "grep",
    "pack_owned",
    "pack_tokens",
    "renamed",
]

# The one capability that Terminal Projection deletes. It is restated here so
# that the suite names it without importing the code it measures.
CAPABILITY = "bootstrap"
SOURCE_DIRECTORY = "src"
INITIAL_DIRECTORY = "initial"
PROJECT_FILE = "pyproject.toml"
SEPARATOR = "/"
ARCHIVE_SUFFIX = ".tar"
LOCAL_REPOSITORY = "local"
PRIVATE_PREFIX = "_"
TYPED_MARKER = "py.typed"
PACK_DIRECTORY = "pack"
# Code D of #81. The projection must build a whole tree with this module on the
# path, so a socket call is an immediate failure rather than a slow timeout.
PROBE_MODULE = "sitecustomize.py"
SOCKET_FAILURE = "the projection opened a socket"
OFFLINE_PROBE = '''"""Refuse every socket, so an offline projection is provable."""

import socket


def _blocked(*args: object, **kwargs: object) -> object:
    raise AssertionError("the projection opened a socket")


socket.socket.connect = _blocked
socket.create_connection = _blocked
'''


@dataclass(frozen=True, slots=True)
class Tokens:
    """The two identity values of one tree: its distribution and its package."""

    project: str
    package: str

    def swaps(self, other: Tokens) -> tuple[tuple[str, str], ...]:
        """The two token pairs, longest first, that turn this identity into *other*."""
        pairs = ((self.project, other.project), (self.package, other.package))
        return tuple(sorted(pairs, key=lambda pair: len(pair[0]), reverse=True))


@dataclass(frozen=True, slots=True)
class Parity:
    """What Code A measured between one Root Pack and one Terminal Project."""

    missing: frozenset[str]
    added: frozenset[str]
    changed: frozenset[str]
    unshadowed: frozenset[str]
    untouched_overlay: frozenset[str]


def pack_tokens(root: Path) -> Tokens:
    """The distribution name and the import package of one tree."""
    project = cast("dict[str, object]", tomllib.loads((root / PROJECT_FILE).read_text("utf-8")))
    metadata = cast("dict[str, object]", project["project"])
    backend = cast("dict[str, object]", cast("dict[str, object]", project["tool"])["uv"])
    build = cast("dict[str, object]", backend["build-backend"])
    return Tokens(project=str(metadata["name"]), package=str(build["module-name"]))


def renamed(relative: str, swaps: tuple[tuple[str, str], ...]) -> str:
    """Rename every path component that equals a pack token (correction C3)."""
    table = dict(swaps)
    return SEPARATOR.join(table.get(part, part) for part in relative.split(SEPARATOR))


def _swapped(data: bytes, swaps: tuple[tuple[str, str], ...]) -> bytes:
    for old, new in swaps:
        data = data.replace(old.encode(), new.encode())
    return data


def _skipped(pack: Tokens) -> tuple[str, ...]:
    """The two locations that projection never carries: the capability and the payload."""
    package_root = f"{SOURCE_DIRECTORY}{SEPARATOR}{pack.package}"
    return (f"{package_root}{SEPARATOR}{CAPABILITY}", package_root)


def _kept(relative: str, pack: Tokens) -> bool:
    capability, package_root = _skipped(pack)
    if relative == capability or relative.startswith(f"{capability}{SEPARATOR}"):
        return False
    inside_package = relative.startswith(f"{package_root}{SEPARATOR}")
    return not (inside_package and relative.endswith(ARCHIVE_SUFFIX))


def _overlay(root: Path, pack: Tokens, swaps: tuple[tuple[str, str], ...]) -> frozenset[str]:
    initial = root / SOURCE_DIRECTORY / pack.package / CAPABILITY / INITIAL_DIRECTORY
    return frozenset(
        renamed(item.relative_to(initial).as_posix(), swaps)
        for item in initial.rglob("*")
        if item.is_file()
    )


def compare(root: Path, project: Path, pack: Tokens, made: Tokens) -> Parity:
    """Code A: the path map, the byte parity, and the overlay closure."""
    swaps = pack.swaps(made)
    expected = {
        renamed(relative, swaps): _swapped((root / relative).read_bytes(), swaps)
        for relative in tracked_files(root)
        if _kept(relative, pack)
    }
    actual = {relative: (project / relative).read_bytes() for relative in present_files(project)}
    overlay = _overlay(root, pack, swaps)
    shared = expected.keys() & actual.keys()
    return Parity(
        missing=frozenset(expected.keys() - actual.keys()),
        added=frozenset(actual.keys() - expected.keys()),
        changed=frozenset(
            relative for relative in shared - overlay if expected[relative] != actual[relative]
        ),
        unshadowed=overlay - expected.keys(),
        untouched_overlay=frozenset(
            relative for relative in shared & overlay if expected[relative] == actual[relative]
        ),
    )


def _digests(members: Iterator[tuple[str, bytes]]) -> Mapping[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in members}


def _members(archive: Path) -> Iterator[tuple[str, bytes]]:
    with tarfile.open(archive) as opened:
        for member in opened.getmembers():
            if not member.isfile():
                continue
            stream = opened.extractfile(member)
            if stream is not None:
                yield member.name, stream.read()


def archive_digests(archive: Path) -> Mapping[str, str]:
    """Code A2: the sha256 of every file member of one archive, keyed by path."""
    return _digests(_members(archive))


def commit_digests(root: Path, destination: Path) -> Mapping[str, str]:
    """Code A2: the same map for `git archive HEAD` of *root*.

    The two maps are compared, never the two archives: archive metadata varies
    between git versions, and the property under test is the tree.
    """
    _ = subprocess.run(
        ("git", "archive", "HEAD", "-o", str(destination)),
        cwd=root,
        check=True,
        capture_output=True,
    )
    return archive_digests(destination)


def grep(tree: Path, pattern: str, *arguments: str) -> tuple[str, ...]:
    """Every line of *tree* that matches *pattern*, git excluded."""
    completed = subprocess.run(
        ("grep", "-rIn", "-E", pattern, str(tree), "--exclude-dir=.git", *arguments),
        capture_output=True,
        text=True,
        check=False,
    )
    return tuple(line for line in completed.stdout.splitlines() if line.strip())


def gate_hook_ids(tree: Path) -> frozenset[str]:
    """Code C: the id of every local hook the gate of *tree* declares."""
    config = cast("dict[str, object]", tomllib.loads((tree / GATE_CONFIG).read_text("utf-8")))
    repositories = cast("list[dict[str, object]]", config["repos"])
    return frozenset(
        str(hook["id"])
        for repository in repositories
        if repository.get("repo") == LOCAL_REPOSITORY
        for hook in cast("list[dict[str, object]]", repository["hooks"])
    )


def pack_owned(rel: str, pkg: str) -> bool:
    """Code E: the ownership predicate, restated so the suite reads no product code."""
    parts = rel.split(SEPARATOR)
    if parts[0] == PACK_DIRECTORY:
        return True
    if parts[:2] == [SOURCE_DIRECTORY, pkg] and len(parts) > 2:
        return parts[2].startswith(PRIVATE_PREFIX) or parts[2] == TYPED_MARKER
    return False


def status_paths(lines: tuple[str, ...]) -> tuple[str, ...]:
    """The repository-relative path of each `git status --porcelain` line."""
    return tuple(re.sub(r"^..\s+", "", line).strip('"') for line in lines)
