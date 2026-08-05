"""The closed outcome vocabulary of the pack-owned command surface.

`ExitCode` classifies the process result. `OutcomeCode` names the failure inside
the machine envelope. `FIXED_OUTCOMES` binds each code to its exit code, its
retryability and its fixed hint.

The table is fixed, and a capability never selects an exit code. The router maps
a raised stdlib exception to one entry of this table (#85 section 3.1).
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "DEPENDENCY_UNAVAILABLE",
    "FIXED_OUTCOMES",
    "INVALID_CONTINUATION",
    "INVALID_SYNTAX",
    "UNEXPECTED_FAILURE",
    "ExitCode",
    "OutcomeCode",
    "OutcomeSpec",
    "PublicDetailValue",
]


class ExitCode(IntEnum):
    """Stable process classifications; the exact meaning stays in the outcome code."""

    SUCCESS = 0
    SYNTAX = 2
    PERMANENT_REJECTION = 3
    TEMPORARY_UNAVAILABLE = 4
    UNEXPECTED_FAILURE = 70


class OutcomeCode(StrEnum):
    """The public failure names that a machine envelope can carry."""

    INVALID_SYNTAX = "invalid_syntax"
    INVALID_CONTINUATION = "invalid_continuation"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    UNEXPECTED_FAILURE = "unexpected_failure"


type PublicDetailValue = str | int | bool | None


@dataclass(frozen=True, slots=True, kw_only=True)
class OutcomeSpec:
    """One outcome code, with its exit code, its retryability and its fixed hint."""

    code: OutcomeCode
    exit_code: ExitCode
    retryable: bool
    hint: str

    def __post_init__(self) -> None:
        if not self.hint.strip():
            raise ValueError("Every outcome states one fixed hint.")
        if self.retryable != (self.exit_code == ExitCode.TEMPORARY_UNAVAILABLE):
            raise ValueError("Only temporary dependency outcomes are retryable.")


INVALID_SYNTAX = OutcomeSpec(
    code=OutcomeCode.INVALID_SYNTAX,
    exit_code=ExitCode.SYNTAX,
    retryable=False,
    hint="Use command help and correct the invocation.",
)
INVALID_CONTINUATION = OutcomeSpec(
    code=OutcomeCode.INVALID_CONTINUATION,
    exit_code=ExitCode.PERMANENT_REJECTION,
    retryable=False,
    hint="Start a new query without --continuation.",
)
DEPENDENCY_UNAVAILABLE = OutcomeSpec(
    code=OutcomeCode.DEPENDENCY_UNAVAILABLE,
    exit_code=ExitCode.TEMPORARY_UNAVAILABLE,
    retryable=True,
    hint="Retry after the local dependency is available.",
)
UNEXPECTED_FAILURE = OutcomeSpec(
    code=OutcomeCode.UNEXPECTED_FAILURE,
    exit_code=ExitCode.UNEXPECTED_FAILURE,
    retryable=False,
    hint="Re-run the command with --debug for a traceback.",
)

FIXED_OUTCOMES: Mapping[OutcomeCode, OutcomeSpec] = MappingProxyType(
    {
        outcome.code: outcome
        for outcome in (
            INVALID_SYNTAX,
            INVALID_CONTINUATION,
            DEPENDENCY_UNAVAILABLE,
            UNEXPECTED_FAILURE,
        )
    }
)
