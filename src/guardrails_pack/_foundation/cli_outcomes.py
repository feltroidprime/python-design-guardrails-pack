"""The closed outcome vocabulary of the pack-owned command surface.

`ExitCode` classifies the process result. `OutcomeCode` names the failure inside
the machine envelope. `FIXED_OUTCOMES` binds each code to its exit code, its
retryability and its fixed hint.

The table is fixed, and a capability never selects an exit code. The router maps
a raised stdlib exception to one entry of this table.

Two codes answer a failure that no capability raises. `permanent_rejection` is
the envelope of a `ValueError` or a `LookupError`. `composition-invalid` is the
envelope of each of the four startup failures of the composition root. The
decision of record spells that one with a hyphen, so this table keeps it
verbatim.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "COMPOSITION_INVALID",
    "DEPENDENCY_UNAVAILABLE",
    "FIXED_OUTCOMES",
    "INVALID_CONTINUATION",
    "INVALID_SYNTAX",
    "PERMANENT_REJECTION",
    "UNEXPECTED_FAILURE",
    "ExitCode",
    "OutcomeCode",
    "OutcomeSpec",
    "PublicDetailValue",
]


class ExitCode(IntEnum):
    """Stable process classifications. The exact meaning stays in the outcome code."""

    SUCCESS = 0
    SYNTAX = 2
    PERMANENT_REJECTION = 3
    TEMPORARY_UNAVAILABLE = 4
    UNEXPECTED_FAILURE = 70


class OutcomeCode(StrEnum):
    """The public failure names that a machine envelope can carry."""

    INVALID_SYNTAX = "invalid_syntax"
    INVALID_CONTINUATION = "invalid_continuation"
    PERMANENT_REJECTION = "permanent_rejection"
    COMPOSITION_INVALID = "composition-invalid"
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
PERMANENT_REJECTION = OutcomeSpec(
    code=OutcomeCode.PERMANENT_REJECTION,
    exit_code=ExitCode.PERMANENT_REJECTION,
    retryable=False,
    hint="Correct the input and run the command again.",
)
COMPOSITION_INVALID = OutcomeSpec(
    code=OutcomeCode.COMPOSITION_INVALID,
    exit_code=ExitCode.PERMANENT_REJECTION,
    retryable=False,
    hint="Repair the composition root, then run the command again.",
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
            PERMANENT_REJECTION,
            COMPOSITION_INVALID,
            DEPENDENCY_UNAVAILABLE,
            UNEXPECTED_FAILURE,
        )
    }
)
