"""Code A, A2, B, C, D and E of #81, as the six supporting checks of the suite.

Each function here answers one question and states no assertion. The test module
that reads the answer holds the assertion, so an assertion always names the
assertion id it carries.

Every reading of a tree here comes from the git index, and that is forced by the
tree rather than chosen. The projection payload is one archive of `HEAD`, so the
file set of the Root Pack is what git tracks, not what the working directory
holds; a virtual environment and every tool cache would otherwise enter the
comparison. The projected tree is read the same way, through the `.gitignore` it
carried, so both sides hold release content and nothing else. `release_files`
gives the word searches of Code B the same file set, for the same reason.

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
    present_locations,
    run,
    tracked_locations,
)

__all__ = [
    "CAPABILITY",
    "OFFLINE_PROBE",
    "PROBE_MODULE",
    "SOCKET_FAILURE",
    "WORKFLOW",
    "Parity",
    "Tokens",
    "archive_digests",
    "collects_nothing",
    "commit_digests",
    "compare",
    "gate_hook_ids",
    "grep",
    "marker_selections",
    "pack_owned",
    "pack_tokens",
    "release_files",
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
# The user-owned workflow, and the pytest policy the gate names in every tree.
# `REM-7` reads the first with the second, so it needs both spellings here.
WORKFLOW = ".github/workflows/quality.yml"
PYTEST_CONFIG = "pack/configs/pytest.ini"
NOTHING_COLLECTED = 5
# A job runs a marker through one pytest command, so the scan reads a `-m`
# option of such a command and never a word of the surrounding prose. The three
# groups are the three ways a workflow can quote the expression.
MARKER_OPTION = re.compile(
    r"""pytest\b[^\n]*?\s-m\s+(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>\S+))"""
)
MARKER_GROUPS = ("double", "single", "bare")
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


def _source_content(path: Path, swaps: tuple[tuple[str, str], ...]) -> bytes:
    """What the projection must write for one file of the Root Pack.

    A symbolic link is release content too, and the projection recreates it with
    both tokens swapped in its own target and every matching path component
    renamed. Reading the link rather than following it is what makes a link to a
    directory comparable at all.
    """
    if path.is_symlink():
        literal = _swapped(str(path.readlink()).encode(), swaps).decode()
        return renamed(literal, swaps).encode()
    return _swapped(path.read_bytes(), swaps)


def _content(path: Path) -> bytes:
    """What one file of a Terminal Project holds, links read and never followed."""
    return str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()


def compare(root: Path, project: Path, pack: Tokens, made: Tokens) -> Parity:
    """Code A: the path map, the byte parity, and the overlay closure."""
    swaps = pack.swaps(made)
    expected = {
        renamed(relative, swaps): _source_content(root / relative, swaps)
        for relative in tracked_locations(root)
        if _kept(relative, pack)
    }
    actual = {relative: _content(project / relative) for relative in present_locations(project)}
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


def release_files(tree: Path, suffixes: tuple[str, ...] = ()) -> tuple[Path, ...]:
    """Every file of *tree* that a word search of #81 may read, relative to it.

    The file set comes from the git index, never from a directory walk. A walk
    reads whatever the working directory happens to hold: a virtual environment,
    every tool cache, and every dependency inside them. Third-party source then
    answers a question that was asked about this product, and no exemption list
    can hold the vocabulary of a package the project did not write.

    A symbolic link is left out. Its own content is the path it names, and the
    file it names is already in this list when the release carries it.
    """
    found = tuple(
        Path(relative)
        for relative in present_locations(tree)
        if not (tree / relative).is_symlink() and (not suffixes or relative.endswith(suffixes))
    )
    if not found:
        raise OSError(f"'{tree}' lists no release file, so a word search would prove nothing.")
    return found


def grep(
    tree: Path, pattern: str, *arguments: str, suffixes: tuple[str, ...] = ()
) -> tuple[str, ...]:
    """Every line of release content of *tree* that matches *pattern*.

    Every scan of #81 measures what a release carries, so the files come from
    `release_files` and each reported path is relative to *tree*. *suffixes*
    narrows the scan to one kind of file, which is how list 2 of Code B reaches
    prose alone.
    """
    files = release_files(tree, suffixes)
    completed = subprocess.run(
        ("grep", "-In", "-E", *arguments, "-e", pattern, "--", *(str(item) for item in files)),
        cwd=tree,
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


def marker_selections(workflow: Path) -> tuple[str, ...]:
    """Every pytest marker expression that the jobs of one workflow file run.

    The reading is textual, because the property under test is what a runner
    executes and a runner reads the same text. A comment that names a marker is
    not a job that runs one, so the scan starts at a `pytest` command.
    """
    text = workflow.read_text(encoding="utf-8")
    found: list[str] = []
    for match in MARKER_OPTION.finditer(text):
        for name in MARKER_GROUPS:
            expression = match.group(name)
            if expression is not None:
                found.append(str(expression))
                break
    return tuple(found)


def collects_nothing(tree: Path, expression: str) -> bool:
    """Whether one marker expression selects no test at all inside *tree*.

    pytest answers exit code 5 for an empty selection, and GitHub Actions reads
    that as a failed job. That is the defect this measurement exists for, so the
    code is read and no output is parsed.
    """
    outcome = run(
        (
            "uv",
            "run",
            "pytest",
            "-c",
            PYTEST_CONFIG,
            "--rootdir=.",
            "--collect-only",
            "-q",
            "-m",
            expression,
        ),
        tree,
    )
    return outcome.code == NOTHING_COLLECTED


def pack_owned(rel: str, pkg: str) -> bool:
    """Code E: the ownership predicate, restated so the suite reads no product code."""
    parts = rel.split(SEPARATOR)
    if parts[0] == PACK_DIRECTORY:
        return True
    if parts[:2] == [SOURCE_DIRECTORY, pkg] and len(parts) > 2:
        return parts[2].startswith(PRIVATE_PREFIX) or parts[2] == TYPED_MARKER
    return False


def status_locations(lines: tuple[str, ...]) -> tuple[str, ...]:
    """The repository-relative path of each `git status --porcelain` line."""
    return tuple(re.sub(r"^..\s+", "", line).strip('"') for line in lines)
