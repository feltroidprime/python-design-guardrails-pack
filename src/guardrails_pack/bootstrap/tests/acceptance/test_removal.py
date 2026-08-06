"""Complete bootstrap removal, `REM-1` to `REM-7`.

The group states that a Terminal Project cannot generate a repository, and
keeps no trace that it once did: no directory, no word, no module, no command,
an empty `CAPABILITIES` tuple, a Root Pack refused as the destination of an
update, and no CI job left behind by the deletion.
"""

from pathlib import Path

from guardrails_pack.bootstrap.tests.acceptance.ban_lists import UNOWNED_TREES, exempt
from guardrails_pack.bootstrap.tests.acceptance.code import (
    CAPABILITY,
    WORKFLOW,
    collects_nothing,
    grep,
    marker_selections,
)
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project
from guardrails_pack.bootstrap.tests.acceptance.harness import porcelain, run
from guardrails_pack.bootstrap.tests.acceptance.packs import Pack

UNKNOWN = "invalid_syntax"


def test_rem_1_no_capability_directory_survives(term: Project) -> None:
    """`REM-1`: invariant `P3`, which refusal `R8` reads inside the projection."""
    found = run(("find", str(term.path), "-type", "d", "-name", CAPABILITY), term.path)

    assert found.out.strip() == ""


def test_rem_2_the_capability_word_does_not_occur(term: Project) -> None:
    """`REM-2`: the downstream recipe is `setup`, so this is a plain word search.

    The scan reads the release files of the project, so the dependencies inside
    its virtual environment answer nothing here. One of them is a test runner
    plugin whose own source carries the word, and this project owns neither that
    source nor its vocabulary.
    """
    found = grep(term.path, CAPABILITY, "-w")

    assert [line for line in found if not exempt(line, *UNOWNED_TREES)] == []


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


def test_rem_7_no_job_runs_a_marker_that_the_deletion_empties(root: Path, term: Project) -> None:
    """`REM-7`: a projected job must have something to run.

    Deleting a capability deletes every test it owns, so a CI job that selects a
    marker of that capability collects nothing. pytest answers exit code 5 and
    the runner fails the job, which makes a new project red on its first push.
    The rule is the class and not one marker: no selection of the projected
    workflow can collect nothing.

    The pack's own workflow is measured against the same project first, so this
    assertion can never pass because it found nothing to measure. That reading
    must collect nothing, because the pack runs a job for the suite this
    capability owns and the project holds no such test.
    """
    empties = [
        expression
        for expression in marker_selections(root / WORKFLOW)
        if collects_nothing(term.path, expression)
    ]
    survivors = [
        expression
        for expression in marker_selections(term.path / WORKFLOW)
        if collects_nothing(term.path, expression)
    ]

    assert empties != []
    assert survivors == []
