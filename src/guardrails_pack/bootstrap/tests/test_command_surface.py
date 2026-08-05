"""The capability as the router renders it: two subcommands, and one envelope.

The router derives the command line from `api.py`, so this capability writes no
command-line code. These cases state what the derivation must give: the three
tokens `<project> bootstrap <function>`, one subcommand per public function, and
a refusal that reaches the caller as the permanent-rejection envelope with exit
code 3 rather than as a traceback.

Every case runs the console script of this project in its own process. A
capability imports no pack code (rule L4 of #85), and the console script is the
seam the acceptance suite of #81 uses as well.
"""

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest

CAPABILITY = "bootstrap"
CONSOLE_SCRIPT = "pyrepo"
SYNTAX_EXIT = 2
PERMANENT_REJECTION_EXIT = 3
NOTHING_WAS_WRITTEN = "Nothing was written."


@pytest.fixture(scope="module")
def console() -> Path:
    """The console script of this project, beside the running interpreter."""
    script = Path(sys.executable).parent / CONSOLE_SCRIPT
    if not script.is_file():
        pytest.skip(f"'{CONSOLE_SCRIPT}' is not installed beside {sys.executable}")
    return script


def run(console: Path, *arguments: str) -> tuple[int, str, dict[str, str]]:
    """Run one command line, and return the exit code, stdout, and the envelope."""
    completed = subprocess.run(
        [str(console), *arguments], capture_output=True, text=True, check=False
    )
    if not completed.stderr:
        return completed.returncode, completed.stdout, {}
    document = cast("dict[str, dict[str, str]]", json.loads(completed.stderr))
    return completed.returncode, completed.stdout, document["error"]


def test_the_router_derives_one_subcommand_per_public_function(console: Path) -> None:
    code, out, _failure = run(console, CAPABILITY, "--help")

    assert code == 0
    assert "init" in out
    assert "release" in out


def test_a_missing_name_is_an_invalid_syntax_envelope(console: Path) -> None:
    code, _out, failure = run(console, CAPABILITY, "init")

    assert code == SYNTAX_EXIT
    assert failure["code"] == "invalid_syntax"


def test_a_refusal_reaches_the_caller_as_a_permanent_rejection(
    console: Path, tmp_path: Path
) -> None:
    code, _out, failure = run(console, CAPABILITY, "init", "1orders", str(tmp_path / "term"))

    assert code == PERMANENT_REJECTION_EXIT
    assert failure["code"] == "permanent_rejection"
    assert failure["message"].startswith("R2:")
    assert failure["message"].endswith(NOTHING_WAS_WRITTEN)
    assert not (tmp_path / "term").exists()


def test_an_existing_destination_is_refused_through_the_router(
    console: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "term"
    destination.mkdir()

    code, _out, failure = run(console, CAPABILITY, "init", "my-product", str(destination))

    assert code == PERMANENT_REJECTION_EXIT
    assert failure["message"].startswith("R5:")
    assert list(destination.iterdir()) == []
