"""Durable local-filesystem implementation of the repository filesystem port."""

import base64
import binascii
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
import tomllib
from typing import Literal, cast, final

from repoctl.modules.repository_generation.application.ports import (
    RepositoryConflictError,
    RepositoryPathEscapeError,
    RepositoryPortError,
    TransactionAlreadyExistsError,
    TransactionInspection,
    TransactionMissingError,
    TransactionState,
    TransactionStateError,
)
from repoctl.modules.repository_generation.domain.intents import (
    CapabilityDeclaration,
    RepositoryFile,
    RepositoryPath,
    RepositorySnapshot,
)
from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipRoot,
    OwnershipZone,
    OwnershipZoneRoots,
    RepositoryPathCandidate,
)

type CapabilityStatus = Literal["draft", "active", "retired"]

_IGNORED_DIRECTORY_NAMES = frozenset(
    {".git", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}
)


@dataclass(frozen=True, slots=True)
class _JournalState:
    """Parsed durable journal facts, including an incomplete final write."""

    state: TransactionState
    entries: tuple[bytes, ...]
    interrupted: bool


@dataclass(frozen=True, slots=True)
class _JournalEvent:
    """One validated, complete append-only journal record."""

    kind: Literal["begin", "entry", "complete", "recovered"]
    entry: bytes | None = None


def _default_ownership_zones(package: str) -> tuple[OwnershipZoneRoots, ...]:
    return (
        OwnershipZoneRoots(
            name=OwnershipZone("FOUNDATION"),
            roots=(OwnershipRoot(value="repoctl"),),
        ),
        OwnershipZoneRoots(
            name=OwnershipZone("PRODUCT"),
            roots=(
                OwnershipRoot(value=f"src/{package}/modules"),
                OwnershipRoot(value="proof/modules"),
                OwnershipRoot(value="tests/modules"),
                OwnershipRoot(value="verification/modules"),
                OwnershipRoot(value="docs/product"),
            ),
        ),
        OwnershipZoneRoots(
            name=OwnershipZone("DERIVED"),
            roots=(
                OwnershipRoot(value=f"src/{package}/_generated"),
                OwnershipRoot(value="proof/_generated"),
                OwnershipRoot(value="docs/architecture/generated"),
            ),
        ),
        OwnershipZoneRoots(
            name=OwnershipZone("DECLARATION"),
            roots=(OwnershipRoot(value=".repo"),),
        ),
    )


def _normalized_location(candidate: RepositoryPathCandidate) -> str:
    value = candidate.value
    drive_absolute = len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] == "/"
    if value.startswith(("/", "\\")) or drive_absolute or "\\" in value:
        raise RepositoryPathEscapeError(f"Repository path escapes its root: {value}")
    segments = tuple(segment for segment in value.split("/") if segment not in {"", "."})
    if not segments or ".." in segments:
        raise RepositoryPathEscapeError(f"Repository path escapes its root: {value}")
    return "/".join(segments)


def _digest(content: bytes) -> str:
    return f"sha256:{sha256(content).hexdigest()}"


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RepositoryPortError(f"{label} must be a TOML table")
    return cast("dict[str, object]", value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise RepositoryPortError(f"{label} must be a string")
    return value


def _texts(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RepositoryPortError(f"{label} must be an array of strings")
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise RepositoryPortError(f"{label} must be an array of strings")
    return tuple(_text(item, label) for item in items)


def _status(value: object) -> CapabilityStatus:
    status = _text(value, "status")
    if status not in {"draft", "active", "retired"}:
        raise RepositoryPortError(f"status is not a known capability state: {status}")
    return cast("CapabilityStatus", status)


def _declaration(content: bytes, location: str) -> CapabilityDeclaration:
    try:
        raw: object = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise RepositoryPortError(f"Cannot read capability declaration {location}") from error
    values = _mapping(raw, location)
    boundaries = _mapping(values.get("boundaries"), f"{location}.boundaries")
    activation = _mapping(values.get("activation"), f"{location}.activation")
    return CapabilityDeclaration(
        name=_text(values.get("name"), f"{location}.name"),
        python_module=_text(values.get("python_module"), f"{location}.python_module"),
        status=_status(values.get("status")),
        proof_catalog=_text(values.get("proof_catalog"), f"{location}.proof_catalog"),
        inbound=_texts(boundaries.get("inbound"), f"{location}.boundaries.inbound"),
        outbound=_texts(boundaries.get("outbound"), f"{location}.boundaries.outbound"),
        api=_text(activation.get("api"), f"{location}.activation.api"),
        factory=_text(activation.get("factory"), f"{location}.activation.factory"),
        cli_catalog=_text(activation.get("cli_catalog"), f"{location}.activation.cli_catalog"),
    )


def _journal_line(values: dict[str, str]) -> bytes:
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def _journal_event(line: bytes, transaction_id: str) -> _JournalEvent | None:
    try:
        raw = cast(object, json.loads(line))
    except UnicodeDecodeError, json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    values = cast("dict[str, object]", raw)
    event = values.get("event")
    if event == "begin":
        return (
            _JournalEvent(kind="begin") if values.get("transaction_id") == transaction_id else None
        )
    if event == "entry":
        encoded = values.get("entry")
        if not isinstance(encoded, str):
            return None
        try:
            return _JournalEvent(
                kind="entry",
                entry=base64.b64decode(encoded.encode("ascii"), validate=True),
            )
        except UnicodeEncodeError, binascii.Error:
            return None
    if event == "complete":
        return _JournalEvent(kind="complete")
    if event == "recovered":
        return _JournalEvent(kind="recovered")
    return None


def _interrupted_journal(state: TransactionState, entries: list[bytes]) -> _JournalState:
    return _JournalState(state=state, entries=tuple(entries), interrupted=True)


def _journal_state(content: bytes, transaction_id: str) -> _JournalState:
    state: TransactionState = "incomplete"
    entries: list[bytes] = []
    began = False
    for line in content.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            return _interrupted_journal(state, entries)
        event = _journal_event(line, transaction_id)
        if event is None:
            return _interrupted_journal(state, entries)
        if event.kind == "begin":
            if began:
                return _interrupted_journal(state, entries)
            began = True
            continue
        if not began or state != "incomplete":
            return _interrupted_journal(state, entries)
        if event.kind == "entry":
            if event.entry is None:
                return _interrupted_journal(state, entries)
            entries.append(event.entry)
            continue
        state = event.kind
    return _JournalState(state=state, entries=tuple(entries), interrupted=not began)


def _fsync_directory(directory: Path) -> None:
    """Request directory metadata durability where the platform supports it."""
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _assert_inside_root(root: Path, path: Path) -> None:
    try:
        resolved = path.resolve(strict=False)
    except OSError as error:
        raise RepositoryPathEscapeError(f"Cannot resolve repository path: {path}") from error
    if not resolved.is_relative_to(root):
        raise RepositoryPathEscapeError(f"Repository path resolves outside its root: {path}")


def _path_for(root: Path, candidate: RepositoryPathCandidate) -> Path:
    location = _normalized_location(candidate)
    path = root.joinpath(*location.split("/"))
    _assert_inside_root(root, path)
    return path


def _transaction_directory(root: Path) -> Path:
    return _path_for(root, RepositoryPathCandidate(value=".repo/transactions"))


def _journal_path(root: Path, transaction_id: str) -> Path:
    digest = sha256(transaction_id.encode("utf-8")).hexdigest()
    return _transaction_directory(root) / f"{digest}.jsonl"


def _read_journal(root: Path, transaction_id: str) -> _JournalState:
    path = _journal_path(root, transaction_id)
    _assert_inside_root(root, path)
    if not path.exists():
        raise TransactionMissingError(f"Transaction does not exist: {transaction_id}")
    try:
        content = path.read_bytes()
    except OSError as error:
        raise RepositoryPortError(f"Cannot inspect transaction: {transaction_id}") from error
    return _journal_state(content, transaction_id)


def _append_journal_event(root: Path, transaction_id: str, values: dict[str, str]) -> None:
    path = _journal_path(root, transaction_id)
    _assert_inside_root(root, path)
    try:
        with path.open("ab") as stream:
            _ = stream.write(_journal_line(values))
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_directory(path.parent)
    except OSError as error:
        raise RepositoryPortError(f"Cannot update transaction: {transaction_id}") from error


def _inspection(transaction_id: str, journal: _JournalState) -> TransactionInspection:
    return TransactionInspection(
        transaction_id=transaction_id,
        state=journal.state,
        entries=journal.entries,
    )


@final
class LocalRepository:
    """A root-confined, fsyncing implementation backed by a real local filesystem."""

    def __init__(
        self,
        *,
        root: Path,
        package: str = "acme",
        ownership_zones: tuple[OwnershipZoneRoots, ...] | None = None,
    ) -> None:
        try:
            root.mkdir(parents=True, exist_ok=True)
            self._root = root.resolve()
        except OSError as error:
            raise RepositoryPortError(f"Cannot initialize repository root: {root}") from error
        if not self._root.is_dir():
            raise RepositoryPortError(f"Repository root is not a directory: {self._root}")
        self._package = package
        self._ownership_zones = (
            _default_ownership_zones(package) if ownership_zones is None else ownership_zones
        )
        self._lock = RLock()

    def _ensure_parent_directory(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RepositoryPortError(
                f"Cannot create repository directory: {path.parent}"
            ) from error
        _assert_inside_root(self._root, path.parent)

    def _read_existing_bytes(self, path: Path) -> bytes | None:
        if not path.exists():
            return None
        if not path.is_file():
            raise RepositoryPortError(f"Repository path is not a file: {path}")
        try:
            return path.read_bytes()
        except OSError as error:
            raise RepositoryPortError(f"Cannot read repository path: {path}") from error

    def _write_atomically(self, path: Path, content: bytes) -> None:
        self._ensure_parent_directory(path)
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".repoctl-tmp",
            )
        except OSError as error:
            raise RepositoryPortError(f"Cannot stage repository write: {path}") from error
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                _ = stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            _assert_inside_root(self._root, path)
            _ = temporary_path.replace(path)
            _fsync_directory(path.parent)
        except OSError as error:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise RepositoryPortError(f"Cannot commit repository write: {path}") from error

    def _repository_files(self) -> tuple[Path, ...]:
        files: list[Path] = []
        transaction_directory = _transaction_directory(self._root)
        for current, directories, names in os.walk(self._root, followlinks=False):
            current_path = Path(current)
            directories[:] = [
                name
                for name in sorted(directories)
                if not (current_path / name).is_symlink()
                and name not in _IGNORED_DIRECTORY_NAMES
                and (current_path / name) != transaction_directory
            ]
            files.extend(
                current_path / name
                for name in sorted(names)
                if not (current_path / name).is_symlink()
            )
        return tuple(files)

    def snapshot(self) -> RepositorySnapshot:
        """Return a canonical immutable view of regular files rooted at this repository."""
        with self._lock:
            contents_by_location: dict[str, bytes] = {}
            for path in self._repository_files():
                location = path.relative_to(self._root).as_posix()
                try:
                    contents_by_location[location] = path.read_bytes()
                except OSError as error:
                    raise RepositoryPortError(f"Cannot snapshot repository path: {path}") from error
            declarations = tuple(
                _declaration(content, location)
                for location, content in contents_by_location.items()
                if location.startswith(".repo/capabilities/") and location.endswith(".toml")
            )
            files = tuple(
                RepositoryFile(
                    path=RepositoryPath(value=location),
                    digest=_digest(content),
                )
                for location, content in contents_by_location.items()
            )
            return RepositorySnapshot(
                schema_version=1,
                package=self._package,
                declarations=declarations,
                files=files,
                ownership_zones=self._ownership_zones,
            )

    def read_bytes(self, repository_path: RepositoryPathCandidate) -> bytes | None:
        """Return current bytes for a normalized path confined to the repository root."""
        with self._lock:
            return self._read_existing_bytes(_path_for(self._root, repository_path))

    def ensure_directory(self, repository_path: RepositoryPathCandidate) -> None:
        """Create a normalized repository-relative directory without following escapes."""
        with self._lock:
            path = _path_for(self._root, repository_path)
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise RepositoryPortError(f"Cannot create repository directory: {path}") from error
            _assert_inside_root(self._root, path)
            _fsync_directory(path.parent)

    def write_if_matches(
        self,
        repository_path: RepositoryPathCandidate,
        content: bytes,
        *,
        expected_digest: str,
    ) -> None:
        """Atomically replace one path only when its current digest matches the precondition."""
        with self._lock:
            path = _path_for(self._root, repository_path)
            current = self._read_existing_bytes(path)
            current_digest = "absent" if current is None else _digest(current)
            if current_digest != expected_digest:
                raise RepositoryConflictError(
                    f"Compare-and-swap conflict for {repository_path.value}: "
                    + f"expected {expected_digest}, found {current_digest}"
                )
            self._write_atomically(path, content)

    def begin_transaction(self, transaction_id: str) -> None:
        """Durably create an incomplete append-only transaction journal."""
        with self._lock:
            directory = _transaction_directory(self._root)
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise RepositoryPortError(
                    f"Cannot create transaction directory: {directory}"
                ) from error
            _assert_inside_root(self._root, directory)
            path = _journal_path(self._root, transaction_id)
            _assert_inside_root(self._root, path)
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError as error:
                raise TransactionAlreadyExistsError(
                    f"Transaction already exists: {transaction_id}"
                ) from error
            except OSError as error:
                raise RepositoryPortError(f"Cannot create transaction: {transaction_id}") from error
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    _ = stream.write(
                        _journal_line({"event": "begin", "transaction_id": transaction_id})
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as error:
                raise RepositoryPortError(f"Cannot begin transaction: {transaction_id}") from error
            _fsync_directory(directory)

    def append_transaction_entry(self, transaction_id: str, entry: bytes) -> None:
        """Durably append one opaque entry while the journal remains intact and incomplete."""
        with self._lock:
            journal = _read_journal(self._root, transaction_id)
            if journal.interrupted:
                raise TransactionStateError(f"Transaction journal is interrupted: {transaction_id}")
            if journal.state != "incomplete":
                raise TransactionStateError(
                    f"Cannot append to {journal.state} transaction: {transaction_id}"
                )
            _append_journal_event(
                self._root,
                transaction_id,
                {"entry": base64.b64encode(entry).decode("ascii"), "event": "entry"},
            )

    def inspect_transaction(self, transaction_id: str) -> TransactionInspection:
        """Report a durable journal without misreporting a truncated write as complete."""
        with self._lock:
            return _inspection(transaction_id, _read_journal(self._root, transaction_id))

    def complete_transaction(self, transaction_id: str) -> None:
        """Append the durable completion marker exactly once."""
        with self._lock:
            journal = _read_journal(self._root, transaction_id)
            if journal.interrupted:
                raise TransactionStateError(f"Transaction journal is interrupted: {transaction_id}")
            if journal.state != "incomplete":
                raise TransactionStateError(
                    f"Cannot complete {journal.state} transaction: {transaction_id}"
                )
            _append_journal_event(self._root, transaction_id, {"event": "complete"})

    def recover_transaction(self, transaction_id: str) -> TransactionInspection:
        """Mark a valid incomplete journal recovered while preserving its opaque entries."""
        with self._lock:
            journal = _read_journal(self._root, transaction_id)
            if journal.interrupted:
                raise TransactionStateError(f"Transaction journal is interrupted: {transaction_id}")
            if journal.state == "incomplete":
                _append_journal_event(self._root, transaction_id, {"event": "recovered"})
                journal = _read_journal(self._root, transaction_id)
            return _inspection(transaction_id, journal)
