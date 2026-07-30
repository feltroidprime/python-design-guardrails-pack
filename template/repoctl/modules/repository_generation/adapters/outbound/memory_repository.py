"""Deterministic in-memory implementation of the repository filesystem port."""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
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

_SNAPSHOT_CONTROL_ARTIFACT_PREFIXES = (".repo/plans/",)


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


@dataclass(slots=True)
class _StoredTransaction:
    """Mutable storage detail hidden behind immutable transaction inspections."""

    state: TransactionState
    entries: list[bytes]


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


def _is_snapshot_control_artifact(location: str) -> bool:
    return location.startswith(_SNAPSHOT_CONTROL_ARTIFACT_PREFIXES)


def _parent_locations(location: str) -> tuple[str, ...]:
    segments = location.split("/")
    return tuple("/".join(segments[:index]) for index in range(1, len(segments)))


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


@final
class MemoryRepository:
    """A lock-protected fake that preserves the local adapter's observable semantics."""

    def __init__(
        self,
        *,
        package: str = "acme",
        ownership_zones: tuple[OwnershipZoneRoots, ...] | None = None,
        initial_contents: Mapping[RepositoryPathCandidate, bytes] | None = None,
        escaped_locations: tuple[RepositoryPathCandidate, ...] = (),
    ) -> None:
        self._package = package
        self._ownership_zones = (
            _default_ownership_zones(package) if ownership_zones is None else ownership_zones
        )
        self._lock = RLock()
        self._contents_by_location: dict[str, bytes] = {}
        self._known_containers: set[str] = set()
        self._escaped_locations = frozenset(
            _normalized_location(candidate) for candidate in escaped_locations
        )
        self._transactions: dict[str, _StoredTransaction] = {}
        for candidate, content in (initial_contents or {}).items():
            location = _normalized_location(candidate)
            self._reject_escaped_location(location)
            if location in self._contents_by_location:
                raise RepositoryConflictError(f"Initial content repeats: {location}")
            self._contents_by_location[location] = content
            self._known_containers.update(_parent_locations(location))

    def _reject_escaped_location(self, location: str) -> None:
        if any(
            location == escaped or location.startswith(f"{escaped}/")
            for escaped in self._escaped_locations
        ):
            raise RepositoryPathEscapeError(
                f"Repository path resolves outside its root: {location}"
            )

    def snapshot(self) -> RepositorySnapshot:
        """Return a canonical immutable view excluding repository-control plan artifacts."""
        with self._lock:
            declarations = tuple(
                _declaration(content, location)
                for location, content in self._contents_by_location.items()
                if location.startswith(".repo/capabilities/") and location.endswith(".toml")
            )
            files = tuple(
                RepositoryFile(
                    path=RepositoryPath(value=location),
                    digest=_digest(content),
                )
                for location, content in self._contents_by_location.items()
                if not _is_snapshot_control_artifact(location)
            )
            return RepositorySnapshot(
                schema_version=1,
                package=self._package,
                declarations=declarations,
                files=files,
                ownership_zones=self._ownership_zones,
            )

    def read_bytes(self, repository_path: RepositoryPathCandidate) -> bytes | None:
        """Return the current bytes for a normalized non-escaping location."""
        location = _normalized_location(repository_path)
        with self._lock:
            self._reject_escaped_location(location)
            return self._contents_by_location.get(location)

    def ensure_directory(self, repository_path: RepositoryPathCandidate) -> None:
        """Record a normalized non-escaping directory as present."""
        location = _normalized_location(repository_path)
        with self._lock:
            self._reject_escaped_location(location)
            self._known_containers.add(location)

    def write_if_matches(
        self,
        repository_path: RepositoryPathCandidate,
        content: bytes,
        *,
        expected_digest: str,
    ) -> None:
        """Atomically replace one location only when its digest matches the precondition."""
        location = _normalized_location(repository_path)
        with self._lock:
            self._reject_escaped_location(location)
            current = self._contents_by_location.get(location)
            current_digest = "absent" if current is None else _digest(current)
            if current_digest != expected_digest:
                raise RepositoryConflictError(
                    f"Compare-and-swap conflict for {location}: "
                    + f"expected {expected_digest}, found {current_digest}"
                )
            self._contents_by_location[location] = content
            self._known_containers.update(_parent_locations(location))

    def begin_transaction(self, transaction_id: str) -> None:
        """Start a distinct incomplete transaction journal."""
        with self._lock:
            if transaction_id in self._transactions:
                raise TransactionAlreadyExistsError(f"Transaction already exists: {transaction_id}")
            self._transactions[transaction_id] = _StoredTransaction(
                state="incomplete",
                entries=[],
            )

    def append_transaction_entry(self, transaction_id: str, entry: bytes) -> None:
        """Append one entry while a transaction remains incomplete."""
        with self._lock:
            transaction = self._transaction(transaction_id)
            if transaction.state != "incomplete":
                raise TransactionStateError(
                    f"Cannot append to {transaction.state} transaction: {transaction_id}"
                )
            transaction.entries.append(entry)

    def inspect_transaction(self, transaction_id: str) -> TransactionInspection:
        """Return an immutable inspection of one durable journal."""
        with self._lock:
            return self._inspection(transaction_id, self._transaction(transaction_id))

    def complete_transaction(self, transaction_id: str) -> None:
        """Mark an incomplete journal complete exactly once."""
        with self._lock:
            transaction = self._transaction(transaction_id)
            if transaction.state != "incomplete":
                raise TransactionStateError(
                    f"Cannot complete {transaction.state} transaction: {transaction_id}"
                )
            transaction.state = "complete"

    def recover_transaction(self, transaction_id: str) -> TransactionInspection:
        """Mark an incomplete journal recovered without changing repository contents."""
        with self._lock:
            transaction = self._transaction(transaction_id)
            if transaction.state == "incomplete":
                transaction.state = "recovered"
            return self._inspection(transaction_id, transaction)

    def _transaction(self, transaction_id: str) -> _StoredTransaction:
        try:
            return self._transactions[transaction_id]
        except KeyError as error:
            raise TransactionMissingError(
                f"Transaction does not exist: {transaction_id}"
            ) from error

    def _inspection(
        self,
        transaction_id: str,
        transaction: _StoredTransaction,
    ) -> TransactionInspection:
        return TransactionInspection(
            transaction_id=transaction_id,
            state=transaction.state,
            entries=tuple(transaction.entries),
        )
