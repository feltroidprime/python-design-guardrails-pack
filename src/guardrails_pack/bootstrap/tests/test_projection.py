"""The four steps of Terminal Projection, and the two source locations.

Each case states one invariant of #85 section 4.1 over the small pack tree of
`conftest.py`: byte parity, no surviving token, the two path renames, the
overlay that only replaces, and no capability directory. The acceptance suite of
#81 states the same invariants over the whole real tree, from the installed
console script.
"""

from pathlib import Path
import socket

import pytest

from guardrails_pack.bootstrap.adapters.outbound.payload import (
    CheckoutPayload,
    InstalledPayload,
    locate_payload,
)
from guardrails_pack.bootstrap.application.creation import (
    Request,
    create_project,
    requested_identity,
)
from guardrails_pack.bootstrap.application.ports import ProjectionPayload
from guardrails_pack.bootstrap.domain.identity import Identity
from guardrails_pack.bootstrap.tests.conftest import (
    CAPABILITY,
    PACK_PACKAGE,
    PACK_PROJECT,
    Recorder,
    build_archive,
    commit_tree,
)

PROJECT = "my-product"
PACKAGE = "my_product"
STARTING = (
    "README.md",
    "CHANGELOG.md",
    f"src/{PACKAGE}/composition.py",
)


def project_once(payload: ProjectionPayload, destination: Path, name: str = PROJECT) -> Path:
    """Run one whole projection with a runner that starts no process."""
    request = Request(
        project=requested_identity(name, ""),
        destination=destination,
        github=False,
        public=False,
    )
    _ = create_project(payload, Recorder(), request)
    return destination


@pytest.fixture
def term(tmp_path: Path, fake_pack: Path) -> Path:
    """One Terminal Project, projected from the shipped-archive source."""
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))
    return project_once(payload, tmp_path / "term")


def relatives(tree: Path) -> set[str]:
    """Every file of one tree, as relative locations."""
    return {
        item.relative_to(tree).as_posix()
        for item in tree.rglob("*")
        if item.is_file() or item.is_symlink()
    }


def test_the_projected_tree_holds_no_pack_token(term: Path) -> None:
    holders = [
        relative
        for relative in relatives(term)
        if PACK_PROJECT in (term / relative).read_text()
        or PACK_PACKAGE in (term / relative).read_text()
    ]

    assert holders == []


def test_every_path_component_equal_to_a_pack_token_is_renamed(term: Path) -> None:
    named = [
        item.relative_to(term).as_posix()
        for item in term.rglob("*")
        if item.name in {PACK_PROJECT, PACK_PACKAGE}
    ]

    assert named == []
    assert (term / "src" / PACKAGE / "cli.py").is_file()


def test_the_path_set_agrees_with_the_pack_after_the_rename(term: Path, fake_pack: Path) -> None:
    dropped = f"src/{PACK_PACKAGE}/{CAPABILITY}/"
    expected = {
        relative.replace(PACK_PACKAGE, PACKAGE)
        for relative in relatives(fake_pack)
        if not relative.startswith(dropped)
    }

    assert relatives(term) == expected


def test_every_file_but_the_three_starting_files_is_the_swapped_pack_file(
    term: Path, fake_pack: Path
) -> None:
    for relative in sorted(relatives(term) - set(STARTING)):
        source = fake_pack / relative.replace(PACKAGE, PACK_PACKAGE)
        want = source.read_bytes().replace(PACK_PROJECT.encode(), PROJECT.encode())

        assert (term / relative).read_bytes() == want.replace(
            PACK_PACKAGE.encode(), PACKAGE.encode()
        )


def test_the_three_starting_files_landed_and_replaced_the_pack_files(
    term: Path, fake_pack: Path
) -> None:
    for relative in STARTING:
        source = fake_pack / relative.replace(PACKAGE, PACK_PACKAGE)
        landed = (term / relative).read_bytes()

        assert landed != source.read_bytes()

    assert "CAPABILITIES = ()" in (term / "src" / PACKAGE / "composition.py").read_text()


def test_no_capability_directory_survives_anywhere(term: Path) -> None:
    surviving = [item for item in term.rglob(CAPABILITY) if item.is_dir()]

    assert surviving == []
    assert not (term / "src" / PACKAGE / CAPABILITY).exists()


def test_the_checkout_source_gives_the_same_tree_as_the_shipped_archive(
    tmp_path: Path, fake_pack: Path, term: Path
) -> None:
    checkout = CheckoutPayload(root=commit_tree(fake_pack))

    second = project_once(checkout, tmp_path / "term2")

    assert relatives(second) == relatives(term)
    for relative in sorted(relatives(second)):
        assert (second / relative).read_bytes() == (term / relative).read_bytes()


def test_a_staged_blob_never_reaches_the_projected_tree(tmp_path: Path, fake_pack: Path) -> None:
    blob = fake_pack / "src" / PACK_PACKAGE / "_pack.tar"
    _ = blob.write_bytes(b"a whole pack tree")
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))

    projected = project_once(payload, tmp_path / "term-blob")

    assert [item.name for item in projected.rglob("_pack.tar")] == []


def test_the_projection_opens_no_socket(tmp_path: Path, fake_pack: Path) -> None:
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))

    def blocked(*_arguments: object, **_keywords: object) -> None:
        raise AssertionError("the projection opened a socket")

    monkeypatched = socket.socket.connect
    socket.socket.connect = blocked
    try:
        projected = project_once(payload, tmp_path / "offline")
    finally:
        socket.socket.connect = monkeypatched

    assert projected.is_dir()


def test_the_projection_source_falls_back_to_the_checkout_of_this_pack() -> None:
    located = locate_payload()

    assert isinstance(located, (InstalledPayload, CheckoutPayload))


def test_a_payload_states_the_two_identity_values_of_its_pack(
    tmp_path: Path, fake_pack: Path
) -> None:
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))

    assert payload.identity() == Identity(project_name=PACK_PROJECT, package=PACK_PACKAGE)


def test_a_symbolic_link_survives_the_projection_as_a_link(tmp_path: Path, fake_pack: Path) -> None:
    link = fake_pack / "docs" / "guide.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(Path("..") / "README.md")
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "linked.tar"))

    projected = project_once(payload, tmp_path / "term-link")

    assert (projected / "docs" / "guide.md").is_symlink()
