"""The nine refusals, and the one promise every one of them ends with.

`R1` to `R6` run before any write. `R7` to `R9` run against the temporary build
directory, and the tree only moves into place after all three pass. Each case
below states one rule, and each case checks the same three facts: the message
names the rule, it ends with the promise, and the destination is absent.

These cases prepare assertion `PAR-11` of #81, which runs the same nine rules
from the installed console script.
"""

from collections.abc import Callable, Mapping
import os
from pathlib import Path

import pytest

from guardrails_pack.bootstrap.adapters.outbound.payload import InstalledPayload
from guardrails_pack.bootstrap.application.creation import (
    Request,
    create_project,
    requested_identity,
)
from guardrails_pack.bootstrap.domain.errors import NOTHING_WAS_WRITTEN, RefusalError
from guardrails_pack.bootstrap.tests.conftest import (
    CAPABILITY,
    PACK_PACKAGE,
    PACK_TREE,
    Recorder,
    build_archive,
    write_tree,
)

STARTING = f"src/{PACK_PACKAGE}/{CAPABILITY}/initial"


def payload_of(tmp_path: Path, contents: Mapping[str, str], name: str) -> InstalledPayload:
    """One projection payload built from one variant of the pack tree."""
    tree = write_tree(tmp_path / name, contents)
    return InstalledPayload(archive=build_archive(tree, tmp_path / f"{name}.tar"))


def refusal(payload: InstalledPayload, destination: Path, project: str) -> str:
    """Run one projection that must refuse, and return the refusal message."""
    request = Request(
        project=requested_identity(project, ""),
        destination=destination,
        github=False,
        public=False,
    )
    with pytest.raises(RefusalError) as raised:
        _ = create_project(payload, Recorder(), request)
    return str(raised.value)


def with_extra(relative: str, text: str) -> dict[str, str]:
    """The pack tree plus one file, which is how each late refusal is provoked."""
    return {**PACK_TREE, relative: text}


NAME_CASES: tuple[tuple[str, str], ...] = (
    ("R1", "-not a name-"),
    ("R2", "1orders"),
    ("R3", "keyword"),
    ("R3", "tomllib"),
    ("R4", "pyrepo"),
)


@pytest.mark.parametrize(("rule", "project"), NAME_CASES)
def test_a_name_rule_refuses_before_any_write(
    tmp_path: Path, fake_pack: Path, rule: str, project: str
) -> None:
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))
    destination = tmp_path / "term"

    message = refusal(payload, destination, project)

    assert message.startswith(f"{rule}:")
    assert message.endswith(NOTHING_WAS_WRITTEN)
    assert not destination.exists()


def test_an_existing_destination_refuses_r5(tmp_path: Path, fake_pack: Path) -> None:
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))
    destination = tmp_path / "term"
    destination.mkdir()
    kept = destination / "precious.txt"
    _ = kept.write_text("do not touch", encoding="utf-8")

    message = refusal(payload, destination, "my-product")

    assert message.startswith("R5:")
    assert message.endswith(NOTHING_WAS_WRITTEN)
    assert list(destination.iterdir()) == [kept]


@pytest.mark.skipif(os.getuid() == 0, reason="root writes a directory with no write bit")
def test_an_unwritable_parent_refuses_r6(tmp_path: Path, fake_pack: Path) -> None:
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))
    closed = tmp_path / "closed"
    closed.mkdir()
    closed.chmod(0o500)
    try:
        message = refusal(payload, closed / "term", "my-product")
    finally:
        closed.chmod(0o700)

    assert message.startswith("R6:")
    assert message.endswith(NOTHING_WAS_WRITTEN)
    assert list(closed.iterdir()) == []


LATE_CASES: tuple[tuple[str, str, Callable[[], dict[str, str]]], ...] = (
    ("R7", "my-product", lambda: dict(PACK_TREE)),
    ("R8", "my-product", lambda: with_extra("docs/bootstrap/notes.md", "A second one.\n")),
    ("R9", "my-product", lambda: with_extra(f"{STARTING}/EXTRA.md", "Shadows nothing.\n")),
)


@pytest.mark.parametrize(("rule", "project", "files"), LATE_CASES)
def test_a_built_tree_rule_refuses_and_leaves_the_destination_absent(
    tmp_path: Path, rule: str, project: str, files: Callable[[], dict[str, str]]
) -> None:
    # R7 fires on a name that contains a pack token: the swap then writes the
    # token back into every file it rewrote. R4 refuses equality only.
    name = "pyrepo-two" if rule == "R7" else project
    payload = payload_of(tmp_path, files(), f"variant-{rule}")
    destination = tmp_path / "term"

    message = refusal(payload, destination, name)

    assert message.startswith(f"{rule}:")
    assert message.endswith(NOTHING_WAS_WRITTEN)
    assert not destination.exists()
    assert [item.name for item in tmp_path.glob(".projection-*")] == []
