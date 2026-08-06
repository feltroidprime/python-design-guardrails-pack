"""Shared violation and evidence-context models for the proof guard.

This is machinery for the three proof rule modules. It defines the
`Violation` shape they all report through. It emits no PROOF code itself.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.proof_catalog import PropertySpec


@dataclass(frozen=True, slots=True, kw_only=True)
class Violation:
    path: Path
    line: int
    code: str
    message: str

    def render(self, root: Path) -> str:
        try:
            relative = self.path.relative_to(root)
        except ValueError:
            relative = self.path
        return f"{relative}:{self.line}: {self.code} {self.message}"


@dataclass(frozen=True, slots=True, kw_only=True)
class TestContext:
    property_spec: PropertySpec
    helper_names: frozenset[str]
    helper_ids: tuple[str, ...]
    invoked_targets: frozenset[str]
    has_assertion: bool

    @property
    def property_id(self) -> str:
        return self.property_spec.property_id


def violation(path: Path, line: int, code: str, message: str) -> Violation:
    return Violation(path=path, line=line, code=code, message=message)


def simple_name(target: str) -> str:
    return target.rpartition(":")[2].rpartition(".")[2]
