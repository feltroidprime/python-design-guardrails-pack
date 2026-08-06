"""Stable machine envelopes and continuation tokens for the command surface.

One success document goes to stdout. One error envelope goes to stderr. A
continuation token is opaque, and it is bound to the query selection that made
it, so a token from one query cannot page another.

The envelope shape is fixed. `write_failure` writes every detail the caller
supplies, because `cli_outcomes` declares no per-outcome key allowlist. A
caller must never put a secret or a local path in a detail value.
"""

import base64
import binascii
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, cast

from .cli_outcomes import OutcomeSpec, PublicDetailValue

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import TextIO

__all__ = [
    "SCHEMA_VERSION",
    "FailureBody",
    "FailureDetail",
    "InvalidContinuationError",
    "decode_continuation",
    "encode_continuation",
    "write_failure",
    "write_success",
]

SCHEMA_VERSION = "1.0"


class InvalidContinuationError(ValueError):
    """Raised when a continuation is malformed or belongs to another query."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason: str = reason


@dataclass(frozen=True, slots=True, kw_only=True)
class FailureDetail:
    """One public key and value that the error envelope carries."""

    key: str
    value: PublicDetailValue


@dataclass(frozen=True, slots=True, kw_only=True)
class FailureBody:
    """One failure, ready to write: its outcome, its message and its details."""

    outcome: OutcomeSpec
    message: str
    details: tuple[FailureDetail, ...] = ()
    hint: str = ""

    @property
    def public_details(self) -> dict[str, PublicDetailValue]:
        return {detail.key: detail.value for detail in self.details}


def write_success(
    *,
    command: str,
    data: object,
    metadata: Mapping[str, object],
    out: TextIO,
) -> None:
    """Write one machine-readable success document and nothing else."""
    document = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "data": data,
        "metadata": dict(metadata),
    }
    _ = out.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_failure(
    *,
    command: str,
    failure: FailureBody,
    err: TextIO,
) -> None:
    """Write one stable machine error envelope exclusively to stderr."""
    document = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "error": {
            "code": failure.outcome.code.value,
            "message": failure.message,
            "retryable": failure.outcome.retryable,
            "hint": failure.hint or failure.outcome.hint,
            "details": failure.public_details,
        },
    }
    _ = err.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")


def encode_continuation(position: str, *, selection: Mapping[str, object]) -> str:
    """Encode an opaque continuation bound to normalized query selection."""
    payload = json.dumps(
        {"position": position, "selection": dict(selection)},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_continuation(token: str, *, selection: Mapping[str, object]) -> str:
    """Return the position only when the token belongs to this selection."""
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode((token + padding).encode()).decode()
        payload = cast("object", json.loads(decoded))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidContinuationError(
            "The continuation token is malformed.", reason="malformed"
        ) from error
    if not isinstance(payload, dict):
        raise InvalidContinuationError("The continuation token is malformed.", reason="malformed")
    document = cast("dict[str, object]", payload)
    position = document.get("position")
    if not isinstance(position, str) or not position:
        raise InvalidContinuationError(
            "The continuation token has no stable position.", reason="missing_position"
        )
    if not position.strip() or any(character in position for character in "\r\n"):
        raise InvalidContinuationError(
            "The continuation token has an invalid position.", reason="invalid_position"
        )
    if document.get("selection") != dict(selection):
        raise InvalidContinuationError(
            "The continuation token belongs to another query.", reason="selection_mismatch"
        )
    return position
