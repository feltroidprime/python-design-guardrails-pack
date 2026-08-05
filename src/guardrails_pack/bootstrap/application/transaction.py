"""One all-or-nothing set of file operations, with the old bytes held in memory.

A Pack Update writes whole files across two zones of a live repository, so it
cannot build the result beside the destination the way a projection does. It
snapshots every path before it touches that path, and it restores every snapshot
on any failure. A crashed update therefore leaves the tree byte-identical and
`git status --porcelain` empty, and the retry succeeds (assertion `UPD-4` of
#81).

The snapshot holds the bytes and the permission bits of a file that existed, or
nothing for a path that did not exist. A restore rewrites the first shape and
deletes the second. Every directory this writer creates is recorded, and a
restore removes each one that is empty again, deepest first.

The pack-owned surface is small text, so the whole snapshot fits in memory. That
is deliberate: a rollback that needs the filesystem can fail exactly when the
filesystem is the thing that failed.
"""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Writer", "transaction"]

PERMISSION_BITS = 0o777


@dataclass(frozen=True, slots=True, kw_only=True)
class Snapshot:
    """The state of one path before the update touched it."""

    data: bytes | None
    mode: int


@dataclass(slots=True, kw_only=True)
class Writer:
    """Every write of one update, with the state to undo all of them."""

    root: Path
    _taken: dict[str, Snapshot] = field(default_factory=dict[str, Snapshot])
    _created: list[Path] = field(default_factory=list[Path])

    def _capture(self, relative: str) -> Path:
        path = self.root / relative
        if relative not in self._taken:
            existing = path.is_file()
            self._taken[relative] = Snapshot(
                data=path.read_bytes() if existing else None,
                mode=path.stat().st_mode & PERMISSION_BITS if existing else 0,
            )
        return path

    def _make_parents(self, path: Path) -> None:
        missing = [parent for parent in (path.parent, *path.parent.parents) if not parent.exists()]
        for parent in reversed(missing):
            parent.mkdir()
            self._created.append(parent)

    def write(self, relative: str, data: bytes, mode: int) -> None:
        """Write one whole file, after the old state of that path is held."""
        path = self._capture(relative)
        self._make_parents(path)
        _ = path.write_bytes(data)
        path.chmod(mode & PERMISSION_BITS)

    def remove(self, relative: str) -> None:
        """Delete one file, after the old state of that path is held."""
        path = self._capture(relative)
        path.unlink(missing_ok=True)

    def restore(self) -> None:
        """Put every touched path back, then drop every directory this writer made."""
        for relative, snapshot in self._taken.items():
            path = self.root / relative
            if snapshot.data is None:
                path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_bytes(snapshot.data)
            path.chmod(snapshot.mode)
        for directory in sorted(self._created, key=lambda entry: len(entry.parts), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()


@contextmanager
def transaction(root: Path) -> Generator[Writer]:
    """Give one writer, and undo every operation of it when the block raises."""
    writer = Writer(root=root)
    try:
        yield writer
    except BaseException:
        writer.restore()
        raise
