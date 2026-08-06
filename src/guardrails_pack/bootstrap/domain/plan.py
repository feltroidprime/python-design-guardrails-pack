"""The write plan of a Pack Update: what changes, what drifted, what is legal.

The plan states one operation per path, and it converges the destination on the
hash list of the installed pack. A clean project gives exactly that
classification, because its bytes are the bytes it was born with. A forced
project gives the same classification plus the repair of every drifted path, so
the manifest is true again after the update rather than at the next release.

Drift is a separate reading: the bytes on disk against the hash list the project
was born with. Three shapes count, and each one makes the manifest lie:

* a pack-owned file whose bytes changed;
* a pack-owned file the record holds and the tree does not;
* a pack-owned file the tree holds and the record does not.

`U6` reads the finished plan through the ownership predicate before any file is
touched. It never reads the manifest's path list: a file that the new version
dropped is absent from that list, and the update must still delete it.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from guardrails_pack.bootstrap.domain.errors import refuse
from guardrails_pack.bootstrap.domain.ownership import pack_owned

__all__ = ["ADD", "DELETE", "REPLACE", "Plan", "build_plan", "check_ownership", "drifted"]

ADD = "add"
REPLACE = "replace"
DELETE = "delete"


@dataclass(frozen=True, slots=True, kw_only=True)
class Plan:
    """One operation per path, in three lists that never overlap."""

    added: tuple[str, ...]
    replaced: tuple[str, ...]
    deleted: tuple[str, ...]

    @property
    def written(self) -> tuple[str, ...]:
        """Every path the update creates or replaces."""
        return (*self.added, *self.replaced)

    @property
    def touched(self) -> tuple[str, ...]:
        """Every path the update writes or removes, in a stable order."""
        return tuple(sorted((*self.added, *self.replaced, *self.deleted)))


def build_plan(
    recorded: Mapping[str, str], shipped: Mapping[str, str], present: Mapping[str, str]
) -> Plan:
    """The operations that turn the present bytes into the bytes of *shipped*."""
    added: list[str] = []
    replaced: list[str] = []
    deleted: list[str] = []
    for path in sorted({*recorded, *shipped, *present}):
        wanted = shipped.get(path)
        current = present.get(path)
        if wanted is None:
            if current is not None:
                deleted.append(path)
        elif current is None:
            added.append(path)
        elif current != wanted:
            replaced.append(path)
    return Plan(added=tuple(added), replaced=tuple(replaced), deleted=tuple(deleted))


def drifted(recorded: Mapping[str, str], present: Mapping[str, str]) -> tuple[str, ...]:
    """Every pack-owned path whose bytes left the record the project was born with."""
    return tuple(
        sorted(path for path in {*recorded, *present} if recorded.get(path) != present.get(path))
    )


def check_ownership(plan: Plan, package: str) -> None:
    """`U6`: refuse a plan that holds one path the ownership predicate forbids."""
    forbidden = tuple(path for path in plan.touched if not pack_owned(path, package))
    if forbidden:
        raise refuse(
            "U6",
            f"The update planned to write '{forbidden[0]}', which you own.",
            "A Pack Update replaces whole pack-owned files and never writes a file of yours.",
            "Report this as a defect of the pack.",
        )
