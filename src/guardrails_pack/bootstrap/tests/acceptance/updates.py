"""Drive one Pack Update from the installed console script, and read its report.

Group 4 of #81 measures the update from the outside only: exit codes, envelopes,
byte comparisons and `git status --porcelain`. This module runs the command and
reads the envelope. It states no assertion.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import cast

from guardrails_pack.bootstrap.tests.acceptance.code import CAPABILITY, pack_owned
from guardrails_pack.bootstrap.tests.acceptance.harness import Outcome, present_files, run
from guardrails_pack.bootstrap.tests.acceptance.packs import Pack

__all__ = [
    "MANIFEST",
    "Report",
    "digests",
    "manifest_of",
    "update",
    "user_owned",
    "write_manifest_record",
]

MANIFEST = "pack/manifest.json"
DATA = "data"
FORCE = "--force"


@dataclass(frozen=True, slots=True)
class Report:
    """One update outcome: its command result, and the document it wrote."""

    outcome: Outcome
    data: Mapping[str, object]

    @property
    def written(self) -> int:
        """How many paths the update wrote, as the update itself counted them."""
        return int(cast("int", self.data.get("written", -1)))

    @property
    def shims(self) -> tuple[Mapping[str, object], ...]:
        """One line per user-owned entry point, which the update never writes."""
        return tuple(cast("list[Mapping[str, object]]", self.data.get("shims", [])))

    def paths(self, key: str) -> tuple[str, ...]:
        """The `added`, `replaced` or `deleted` list of the report, as paths."""
        return tuple(str(item) for item in cast("list[object]", self.data.get(key, [])))

    @property
    def planned(self) -> tuple[str, ...]:
        """Every path the update planned to write or remove."""
        return (*self.paths("added"), *self.paths("replaced"), *self.paths("deleted"))


def update(pack: Pack, tree: Path, *, force: bool = False) -> Report:
    """Run one update of *tree* from the installed console script of *pack*."""
    flags = (FORCE,) if force else ()
    outcome = run((str(pack.script), CAPABILITY, "update", str(tree), *flags), tree)
    data: Mapping[str, object] = {}
    for line in outcome.out.splitlines():
        document = cast("dict[str, object]", json.loads(line)) if line.startswith("{") else {}
        if DATA in document:
            data = cast("Mapping[str, object]", document[DATA])
    return Report(outcome=outcome, data=data)


def digests(tree: Path, package: str, *, owned: bool) -> dict[str, str]:
    """The sha256 of every release file of one ownership zone of *tree*."""
    return {
        relative: sha256((tree / relative).read_bytes()).hexdigest()
        for relative in present_files(tree)
        if pack_owned(relative, package) is owned and (tree / relative).is_file()
    }


def user_owned(tree: Path, package: str) -> dict[str, str]:
    """The sha256 of every user-owned file, which an update must never change."""
    return digests(tree, package, owned=False)


def manifest_of(tree: Path) -> dict[str, object]:
    """The record that the project was born with."""
    return cast("dict[str, object]", json.loads((tree / MANIFEST).read_text("utf-8")))


def write_manifest_record(tree: Path, record: Mapping[str, object]) -> Path:
    """Rewrite the record of *tree*, for the refusals that read a broken one."""
    target = tree / MANIFEST
    _ = target.write_text(json.dumps(dict(record), indent=2, sort_keys=True) + "\n", "utf-8")
    return target
