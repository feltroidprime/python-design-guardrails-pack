"""The two projection source locations, and the one tree they both give.

Installed, the payload is the archive the wheel ships at `<package>/_pack.tar`.
In the Root Pack's own checkout that archive is absent, and the code falls back
to the repository root. The acceptance suite exercises both sources.

Both locations give the tree of one commit. The installed archive is
`git archive HEAD` of the release, and the checkout builds the same archive on
demand, so the two sources cannot drift apart. The staged archive itself is
dropped on the way out, so an interrupted build never ships the whole Root Pack
inside a Terminal Project.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import tarfile
import tempfile
import tomllib
from typing import cast

from guardrails_pack.bootstrap.adapters.outbound.commands import output
from guardrails_pack.bootstrap.domain.identity import Identity
from guardrails_pack.bootstrap.domain.projection import BLOB_NAME, is_staged_blob

__all__ = [
    "CheckoutPayload",
    "InstalledPayload",
    "checkout_root",
    "locate_payload",
    "package_root",
]

PROJECT_FILE = "pyproject.toml"
PACK_DIRECTORY = "pack"
ARCHIVE_NAME = "payload.tar"
CURRENT_PREFIX = "./"
# Depth of this module below the import package: adapters/outbound/payload.py.
PACKAGE_DEPTH = 3
ROOT_DEPTH = 5


def _table(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OSError(f"{PROJECT_FILE} of the pack is not readable as a table.")
    return cast("dict[str, object]", value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise OSError(f"{PROJECT_FILE} of the pack states no name.")
    return value


def _identity_of(data: bytes) -> Identity:
    """The two identity values of the pack, read from its own project file."""
    raw = _table(tomllib.loads(data.decode()))
    backend = _table(_table(_table(raw["tool"])["uv"])["build-backend"])
    return Identity(
        project_name=_text(_table(raw["project"])["name"]),
        package=_text(backend["module-name"]),
    )


def _wanted(archive: tarfile.TarFile) -> Iterator[tarfile.TarInfo]:
    """Every member but the staged archive, with a leading './' removed."""
    for member in archive:
        member.name = member.name.removeprefix(CURRENT_PREFIX)
        if member.name and not is_staged_blob(member.name):
            yield member


def _unpack_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as opened:
        opened.extractall(destination, members=_wanted(opened), filter="data")


def _read_member(archive: Path, name: str) -> bytes:
    with tarfile.open(archive) as opened:
        extracted = opened.extractfile(name)
        if extracted is None:
            raise OSError(f"The projection payload holds no '{name}'.")
        with extracted:
            return extracted.read()


@dataclass(frozen=True, slots=True, kw_only=True)
class InstalledPayload:
    """The archive that the wheel ships inside the import package."""

    archive: Path

    def identity(self) -> Identity:
        """The two identity values of the pack this payload carries."""
        return _identity_of(_read_member(self.archive, PROJECT_FILE))

    def unpack(self, destination: Path, /) -> None:
        """Write the whole Root Pack tree below *destination*, blob excluded."""
        _unpack_archive(self.archive, destination)


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckoutPayload:
    """The Root Pack's own checkout, used when the shipped archive is absent."""

    root: Path

    def _git(self, *arguments: str) -> bytes:
        return output(("git", *arguments), self.root)

    def identity(self) -> Identity:
        """The two identity values of the pack this payload carries."""
        return _identity_of(self._git("show", f"HEAD:{PROJECT_FILE}"))

    def unpack(self, destination: Path, /) -> None:
        """Write the whole Root Pack tree below *destination*, blob excluded."""
        with tempfile.TemporaryDirectory() as workspace:
            archive = Path(workspace) / ARCHIVE_NAME
            _ = self._git("archive", "HEAD", "-o", str(archive))
            _unpack_archive(archive, destination)


def package_root() -> Path:
    """The import package that carries this capability."""
    return Path(__file__).resolve().parents[PACKAGE_DEPTH]


def checkout_root() -> Path:
    """The Root Pack's own checkout. Raise `OSError` when this run has none."""
    root = Path(__file__).resolve().parents[ROOT_DEPTH]
    if not (root / PROJECT_FILE).is_file() or not (root / PACK_DIRECTORY).is_dir():
        raise OSError(f"'{root}' is not the checkout of a pack.")
    return root


def locate_payload() -> InstalledPayload | CheckoutPayload:
    """The projection source of this run: the shipped archive, or the checkout."""
    archive = package_root() / BLOB_NAME
    if archive.is_file():
        return InstalledPayload(archive=archive)
    return CheckoutPayload(root=checkout_root())
