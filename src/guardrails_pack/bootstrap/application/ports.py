"""The two ports of the capability: the projection payload and one command.

A port is a `Protocol`, so this layer names no adapter and the composition in
`api.py` supplies the implementation. Both ports raise `OSError` on failure. The
router maps `OSError` to the retryable `dependency_unavailable` envelope and to
exit code 4 (#85 section 3.1), which is the truth for a missing `git`, a missing
`just`, or a command that ends non-zero.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from guardrails_pack.bootstrap.domain.identity import Identity

__all__ = ["CommandRunner", "ProjectionPayload"]


class ProjectionPayload(Protocol):
    """The Root Pack tree, from one of the two projection source locations."""

    def identity(self) -> Identity:
        """The two identity values of the pack this payload carries."""
        ...

    def unpack(self, destination: Path, /) -> None:
        """Write the whole Root Pack tree below *destination*, blob excluded."""
        ...


class CommandRunner(Protocol):
    """One local command, run in one directory, with no network of its own."""

    def run(self, command: Sequence[str], directory: Path, /) -> None:
        """Run one command. Raise `OSError` when it is absent or ends non-zero."""
        ...

    def succeeds(self, command: Sequence[str], directory: Path, /) -> bool:
        """Run one command and report whether it ended with zero."""
        ...
