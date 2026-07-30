"""Application-owned effects required to inspect and update a repository.

The port deliberately exposes only repository-wide, implementation-independent
behavior.  In particular, transaction entries are opaque bytes: the journal
application service owns their record format while adapters own durable storage
and recovery of those bytes.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from repoctl.modules.repository_generation.domain.intents import RepositorySnapshot
from repoctl.modules.repository_generation.domain.ownership import RepositoryPathCandidate

type TransactionState = Literal["incomplete", "complete", "recovered"]


class RepositoryPortError(RuntimeError):
    """Base class for failures at the repository filesystem boundary."""


class RepositoryConflictError(RepositoryPortError):
    """Raised when a compare-and-swap precondition does not match current bytes."""


class RepositoryPathEscapeError(RepositoryPortError):
    """Raised when a path resolves outside the configured repository root."""


class RepositoryTransactionError(RepositoryPortError):
    """Base class for durable transaction-journal failures."""


class TransactionAlreadyExistsError(RepositoryTransactionError):
    """Raised when a caller starts a transaction identifier more than once."""


class TransactionMissingError(RepositoryTransactionError):
    """Raised when a caller requests a transaction that does not exist."""


class TransactionStateError(RepositoryTransactionError):
    """Raised when a transaction operation is invalid for its current state."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionInspection:
    """The durable state and opaque journal entries for one transaction."""

    transaction_id: str
    state: TransactionState
    entries: tuple[bytes, ...]


class RepositoryPort(Protocol):
    """Filesystem and journal behavior required by repository-generation use cases."""

    def snapshot(self) -> RepositorySnapshot:
        """Return canonical current repository state for planning and verification."""
        ...

    def read_bytes(self, repository_path: RepositoryPathCandidate) -> bytes | None:
        """Return the bytes at one normalized repository-relative path, if present."""
        ...

    def ensure_directory(self, repository_path: RepositoryPathCandidate) -> None:
        """Create a normalized repository-relative directory when it is absent."""
        ...

    def write_if_matches(
        self,
        repository_path: RepositoryPathCandidate,
        content: bytes,
        *,
        expected_digest: str,
    ) -> None:
        """Write bytes only when the current state is absent or has the expected digest.

        ``expected_digest`` is either ``"absent"`` or the SHA-256 digest of the
        existing bytes.  Implementations must create needed parent directories,
        normalize redundant current-directory segments, and reject paths that
        escape the repository root.
        """
        ...

    def begin_transaction(self, transaction_id: str) -> None:
        """Create a durable, initially incomplete journal for one transaction."""
        ...

    def append_transaction_entry(self, transaction_id: str, entry: bytes) -> None:
        """Append one opaque application-owned journal entry in call order."""
        ...

    def inspect_transaction(self, transaction_id: str) -> TransactionInspection:
        """Report durable transaction state without treating an incomplete journal as done."""
        ...

    def complete_transaction(self, transaction_id: str) -> None:
        """Durably mark an incomplete transaction journal complete."""
        ...

    def recover_transaction(self, transaction_id: str) -> TransactionInspection:
        """Preserve an interrupted journal's entries and mark it recovered.

        Recovery changes journal state only; it must never write or rewrite a
        product path that was not explicitly requested by an application use
        case.
        """
        ...
