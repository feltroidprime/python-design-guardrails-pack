"""Group 2 of #81: complete bootstrap removal, `REM-1` to `REM-6`.

The group certifies that a Terminal Project cannot generate a repository and
does not remember that it ever could: no directory, no word, no module, no
command, an empty `CAPABILITIES` tuple, and a Root Pack refused as the
destination of an update (#85 sections 2.2 and 3.2).
"""

from pathlib import Path

from guardrails_pack.bootstrap.tests.acceptance.ban_lists import UNOWNED_TREES
from guardrails_pack.bootstrap.tests.acceptance.code import CAPABILITY
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project
from guardrails_pack.bootstrap.tests.acceptance.harness import porcelain, run
from guardrails_pack.bootstrap.tests.acceptance.packs import Pack

UNKNOWN = "invalid_syntax"


def test_rem_1_no_capability_directory_survives(term: Project) -> None:
    """`REM-1`: invariant `P3`, which refusal `R8` reads inside the projection."""
    found = run(("find", str(term.path), "-type", "d", "-name", CAPABILITY), term.path)

    assert found.out.strip() == ""


def test_rem_2_the_capability_word_does_not_occur(term: Project) -> None:
    """`REM-2`: the downstream recipe is `setup`, so this is a plain word search."""
    found = run(
        ("grep", "-rIn", "-w", CAPABILITY, str(term.path), "--exclude-dir=.git"),
        term.path,
    )
    owned = [
        line
        for line in found.out.splitlines()
        if not any(f"/{tree}/" in line for tree in UNOWNED_TREES)
    ]

    assert owned == []


def test_rem_3_the_module_is_gone(term: Project) -> None:
    """`REM-3`: no importable remnant of the deleted capability."""
    imported = run(
        ("uv", "run", "python", "-c", f"import {term.tokens.package}.{CAPABILITY}"),
        term.path,
    )

    assert imported.code != 0
    assert "ModuleNotFoundError" in imported.text


def test_rem_4_the_command_is_gone(term: Project) -> None:
    """`REM-4`: the router derives no subcommand for a capability nothing composes."""
    listing = run(("uv", "run", term.tokens.project, "--help"), term.path)
    called = run(
        ("uv", "run", term.tokens.project, CAPABILITY, "init", "x"),
        term.path,
    )

    assert listing.code == 0, listing.text
    assert CAPABILITY not in listing.out
    assert called.code != 0
    assert UNKNOWN in called.text


def test_rem_5_the_seeded_composition_root_composes_nothing(term: Project) -> None:
    """`REM-5`: the overlay reseeds the composition root, so it starts empty."""
    read = run(
        (
            "uv",
            "run",
            "python",
            "-c",
            f"import {term.tokens.package}.composition as c; assert c.CAPABILITIES == ()",
        ),
        term.path,
    )

    assert read.code == 0, read.text


def test_rem_6_a_root_pack_is_refused_as_a_destination(root: Path, toolenv: Pack) -> None:
    """`REM-6`: refusal `U7`, so a pack can never update itself."""
    before = porcelain(root)

    refused = run((str(toolenv.script), CAPABILITY, "update", str(root)), root)

    assert refused.code != 0
    assert "U7: " in refused.text
    assert porcelain(root) == before
