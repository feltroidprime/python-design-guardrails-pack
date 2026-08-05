"""The pack-owned router seam, driven as a process.

Every assertion here runs the router in a subprocess and reads its exit code and
its envelope, because those two are the whole contract of the seam. The tests
name no package: `discover_package` reads it from `src/`, exactly as every other
pack-owned script does.

The driver below composes a synthetic capability. A real capability directory
would need layers, a `proof.toml` and a composed import, and none of those change
what the router reads: an entry's module name, its docstring, and the signature
and docstring of each public function.

`CLI001` to `CLI004` refuse an unrenderable api surface at the gate, and
`test_cli_surface.py` proves each of those four rules. The refusals proved here
are the router's own second line of defense.
"""

import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import cast

import pytest

from scripts.identity import discover_capabilities, discover_package

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = discover_package(REPOSITORY_ROOT)
FOUNDATION = REPOSITORY_ROOT / "src" / PACKAGE / "_foundation"

DRIVER = '''"""Compose one synthetic capability, then run the router."""

import importlib
import sys
import types
from collections.abc import Iterator

package = sys.argv[1]
mode = sys.argv[2]

ERRORS = {
    "value": ValueError("bad value"),
    "lookup": LookupError("no key"),
    "connection": ConnectionError("no server"),
    "other": RuntimeError("boom"),
}


def show(name: str, /, times: int = 1, *, loud: bool = False) -> dict[str, object]:
    """Show one greeting."""
    return {"name": name, "times": times, "loud": loud}


def listing(prefix: str = "x") -> Iterator[str]:
    """List seven values."""
    return iter(prefix + str(number) for number in range(7))


def fail(kind: str) -> str:
    """Raise one mapped exception."""
    raise ERRORS[kind]


def paged(limit: int = 1) -> str:
    """Claim a reserved router option."""
    return "never"


class Service:
    """A bound object that a factory of the same capability builds."""

    def report(self) -> str:
        """Report one line."""
        return "ok"


api = types.ModuleType(package + ".demo.api")
api.__doc__ = "The demo capability."
functions = [show, listing, fail]
if mode == "reserved":
    functions.append(paged)
for function in functions:
    function.__module__ = api.__name__
    setattr(api, function.__name__, function)
Service.__module__ = package + ".demo.application.service"

entries = {
    "one": (api,),
    "twice": (api, api),
    "collision": (api, Service()),
    "reserved": (api,),
}[mode]

composition = types.ModuleType(package + ".composition")
composition.CAPABILITIES = entries
sys.modules[package + ".composition"] = composition

router = importlib.import_module(package + "._foundation.router")
raise SystemExit(router.main(sys.argv[3:]))
'''


@pytest.fixture(scope="session")
def driver(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The one driver script that every process assertion runs."""
    path = tmp_path_factory.mktemp("router") / "driver.py"
    _ = path.write_text(DRIVER, encoding="utf-8")
    return path


def run(driver: Path, mode: str, *argv: str) -> subprocess.CompletedProcess[str]:
    """Run the router in one process, with the synthetic capability composed."""
    return subprocess.run(
        (sys.executable, str(driver), PACKAGE, mode, *argv),
        capture_output=True,
        text=True,
        check=False,
        cwd=REPOSITORY_ROOT,
    )


def envelope(text: str) -> dict[str, object]:
    """The one machine document that a stream carries."""
    document = cast("object", json.loads(text.strip().splitlines()[-1]))
    assert isinstance(document, dict)
    return cast("dict[str, object]", document)


def error_code(completed: subprocess.CompletedProcess[str]) -> object:
    """The outcome code of the failure envelope on stderr."""
    failure = envelope(completed.stderr)["error"]
    assert isinstance(failure, dict)
    return cast("dict[str, object]", failure)["code"]


def imported_modules(path: Path) -> set[str]:
    """Every module of this package that one source file imports statically."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return {name for name in names if name.split(".")[0] == PACKAGE}


def test_the_foundation_imports_no_user_module_statically() -> None:
    """Every static import of the foundation stays inside the foundation."""
    outside = {
        name
        for path in FOUNDATION.rglob("*.py")
        for name in imported_modules(path)
        if name.split(".")[1:2] != ["_foundation"]
    }

    assert outside == set()


def test_the_foundation_imports_one_user_owned_module_at_run_time() -> None:
    """The composition root is the one user-owned module the router imports."""
    read = f"import importlib;print(importlib.import_module('{PACKAGE}._foundation.router').COMPOSITION_MODULE)"

    completed = subprocess.run(
        (sys.executable, "-c", read),
        capture_output=True,
        text=True,
        check=True,
        cwd=REPOSITORY_ROOT,
    )

    assert completed.stdout.strip() == f"{PACKAGE}.composition"


def test_the_foundation_names_no_capability() -> None:
    """No file of the foundation holds the name of a capability directory."""
    capabilities = discover_capabilities(REPOSITORY_ROOT, PACKAGE)
    sources = [path.read_text(encoding="utf-8") for path in FOUNDATION.rglob("*.py")]

    named = [name for name in capabilities if any(name in source for source in sources)]

    assert named == []


def test_the_help_of_a_zero_capability_project_names_no_capability() -> None:
    """The seeded composition root composes nothing, so the help lists nothing."""
    completed = subprocess.run(
        (
            sys.executable,
            "-c",
            f"from {PACKAGE}.cli import main;raise SystemExit(main(['--help']))",
        ),
        capture_output=True,
        text=True,
        check=False,
        cwd=REPOSITORY_ROOT,
    )

    assert completed.returncode == 0
    assert "capability" in completed.stdout
    assert "demo" not in completed.stdout


def test_the_help_names_the_composed_capability_and_its_functions(driver: Path) -> None:
    completed = run(driver, "one", "--help")

    assert completed.returncode == 0
    assert "demo" in completed.stdout
    assert "The demo capability." in completed.stdout


def test_the_group_help_names_one_subcommand_per_public_function(driver: Path) -> None:
    completed = run(driver, "one", "demo", "--help")

    assert completed.returncode == 0
    for name in ("show", "listing", "fail"):
        assert name in completed.stdout


def test_a_command_writes_one_success_document(driver: Path) -> None:
    completed = run(driver, "one", "demo", "show", "world", "--times", "3")

    assert completed.returncode == 0
    assert envelope(completed.stdout)["data"] == {"name": "world", "times": 3, "loud": False}


def test_a_bool_parameter_becomes_a_presence_flag(driver: Path) -> None:
    """`CLI004` holds the `False` default, so the flag only ever turns it on."""
    completed = run(driver, "one", "demo", "show", "world", "--loud")

    assert completed.returncode == 0
    assert envelope(completed.stdout)["data"] == {"name": "world", "times": 1, "loud": True}


def test_a_presence_flag_takes_no_value(driver: Path) -> None:
    completed = run(driver, "one", "demo", "show", "world", "--loud", "yes")

    assert completed.returncode == 2
    assert error_code(completed) == "invalid_syntax"


@pytest.mark.parametrize(
    ("kind", "code", "outcome"),
    [
        ("value", 3, "permanent_rejection"),
        ("lookup", 3, "permanent_rejection"),
        ("connection", 4, "dependency_unavailable"),
        ("other", 70, "unexpected_failure"),
    ],
)
def test_the_exception_table_maps_each_raised_error(
    driver: Path, kind: str, code: int, outcome: str
) -> None:
    """The capability raises a stdlib exception and never selects an exit code."""
    completed = run(driver, "one", "demo", "fail", "--kind", kind)

    assert completed.returncode == code
    assert error_code(completed) == outcome


def test_an_argparse_rejection_gives_the_syntax_envelope(driver: Path) -> None:
    completed = run(driver, "one", "unknown", "show")

    assert completed.returncode == 2
    assert error_code(completed) == "invalid_syntax"
    assert "Traceback" not in completed.stderr


def test_a_query_pages_with_a_selection_bound_token(driver: Path) -> None:
    """An `Iterator[...]` return adds `--limit` and `--continuation`."""
    first = run(driver, "one", "demo", "listing", "--limit", "3")
    metadata = envelope(first.stdout)["metadata"]
    assert isinstance(metadata, dict)
    token = cast("dict[str, object]", metadata)["continuation"]
    assert isinstance(token, str)

    second = run(driver, "one", "demo", "listing", "--limit", "3", "--continuation", token)

    assert first.returncode == 0
    assert envelope(first.stdout)["data"] == ["x0", "x1", "x2"]
    assert envelope(second.stdout)["data"] == ["x3", "x4", "x5"]


def test_a_query_reports_the_last_page_with_an_empty_token(driver: Path) -> None:
    completed = run(driver, "one", "demo", "listing", "--limit", "50")

    metadata = envelope(completed.stdout)["metadata"]
    assert metadata == {"count": 7, "continuation": ""}


def test_a_malformed_continuation_gives_its_own_envelope(driver: Path) -> None:
    completed = run(driver, "one", "demo", "listing", "--continuation", "not-a-token")

    assert completed.returncode == 3
    assert error_code(completed) == "invalid_continuation"


def test_a_document_command_carries_no_paging_option(driver: Path) -> None:
    """Only a query takes `--limit` and `--continuation`."""
    completed = run(driver, "one", "demo", "show", "--help")

    assert "--limit" not in completed.stdout
    assert "--continuation" not in completed.stdout


def test_every_command_carries_the_two_router_options(driver: Path) -> None:
    completed = run(driver, "one", "demo", "show", "--help")

    assert "--format" in completed.stdout
    assert "--debug" in completed.stdout


def test_a_duplicate_entry_dedupes_by_identity(driver: Path) -> None:
    completed = run(driver, "twice", "demo", "show", "world")

    assert completed.returncode == 0
    assert envelope(completed.stdout)["data"] == {"name": "world", "times": 1, "loud": False}


def test_two_entries_of_one_group_name_the_collision(driver: Path) -> None:
    completed = run(driver, "collision", "demo", "show", "world")

    assert completed.returncode != 0
    assert error_code(completed) == "composition-invalid"
    assert f"{PACKAGE}.demo.api" in completed.stderr
    assert f"{PACKAGE}.demo.application.service" in completed.stderr


def test_a_reserved_parameter_name_is_refused(driver: Path) -> None:
    """The gate refuses this with `CLI001`; the router refuses it again."""
    completed = run(driver, "reserved", "demo", "show", "world")

    assert completed.returncode != 0
    assert error_code(completed) == "composition-invalid"
    assert "limit" in completed.stderr


def test_an_absent_composition_root_gives_an_envelope(tmp_path: Path) -> None:
    """The router answers a missing composition root, and never a traceback."""
    source = tmp_path / "src"
    _ = shutil.copytree(REPOSITORY_ROOT / "src" / PACKAGE, source / PACKAGE)
    (source / PACKAGE / "composition.py").unlink()

    completed = subprocess.run(
        (
            sys.executable,
            "-c",
            f"from {PACKAGE}.cli import main;raise SystemExit(main(['--help']))",
        ),
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env=os.environ | {"PYTHONPATH": str(source)},
    )

    assert completed.returncode != 0
    assert error_code(completed) == "composition-invalid"
    assert "Traceback" not in completed.stderr
