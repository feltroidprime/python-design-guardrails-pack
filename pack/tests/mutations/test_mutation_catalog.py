"""Audit the mutation catalog without duplicating the test suite it points at.

The catalog names each mutation this architecture can suffer and the one
deterministic test that kills it. This module reads the catalog, not the killer:
it proves that every entry names a test that exists, and that the entry names it
in the one runnable command form.

Ticket I10 re-derived the catalog. Ten of the fourteen earlier entries named
plan, apply, derived-index, or lifecycle machinery, all of which tickets I1 to I9
deleted, so none of them has a killer any more. The four survivors point at live
tests, and the one capability entry splits into the five defects that the six
`import-linter` contracts now kill. Assertions `FSC-1` to `FSC-5` of #81 measure
the same five defects from the installed console script.

Every evidence path is under `pack/`, so this pack-owned fixture carries no
identity token and a Terminal Project can read it unchanged.
"""

import ast
import json
from pathlib import Path
from typing import cast

import pytest

PACK_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PACK_ROOT.parent
CATALOG_PATH = PACK_ROOT / "tests/fixtures/mutation_catalog.json"
PACK_DIRECTORY = "pack"
COMMAND_PREFIX = "uv run pytest -c pack/configs/pytest.ini --rootdir=. -q"
ALLOWED_MECHANISMS = frozenset(
    {
        "contract_test",
        "crosshair",
        "guard",
        "hypothesis_property",
        "proof_gate",
    }
)
# The machinery that tickets I1 to I9 deleted. An entry whose id or prose holds
# one of these words names a subsystem that no longer exists, so it can name no
# killer either. The scope clause of ticket I10 states it: the catalog holds no
# plan, apply, or index mutation.
DELETED_MACHINERY = ("plan", "apply", "index", "declaration", "activation", "retirement")
EXPECTED_MUTATIONS = (
    ("capability-layer-missing", "a capability layer directory is absent"),
    ("capability-layer-empty", "a capability layer directory holds no module"),
    ("capability-sibling-import", "one capability imports a sibling capability"),
    (
        "capability-internals-import",
        "the composition root reaches past a capability's public surface",
    ),
    ("capability-imports-pack-code", "one capability imports pack-owned code"),
    (
        "cli-reserved-parameter-name",
        "a command surface takes a parameter name the router reserves",
    ),
    ("oracle-always-true", "an oracle returns True"),
    (
        "pure-target-without-crosshair",
        "a pure target is removed from CrossHair coverage",
    ),
)


def _load_catalog() -> tuple[dict[str, object], ...]:
    document = cast("object", json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
    assert isinstance(document, dict)
    mutations = cast("dict[str, object]", document).get("mutations")
    assert isinstance(mutations, list)
    entries = cast("list[object]", mutations)
    assert all(isinstance(entry, dict) for entry in entries)
    return tuple(cast("dict[str, object]", entry) for entry in entries)


def _text(entry: dict[str, object], key: str) -> str:
    value = entry.get(key)
    assert isinstance(value, str)
    assert value
    return value


def _evidence_source(entry: dict[str, object]) -> tuple[Path, str]:
    evidence = _text(entry, "evidence")
    relative, separator, test_name = evidence.partition("::")
    assert separator
    assert relative.split("/")[0] == PACK_DIRECTORY
    return REPOSITORY_ROOT / relative, test_name


CATALOG = _load_catalog()


def test_the_catalog_holds_the_re_derived_mutations() -> None:
    observed = tuple((_text(entry, "id"), _text(entry, "mutation")) for entry in CATALOG)

    assert observed == EXPECTED_MUTATIONS


@pytest.mark.parametrize("entry", CATALOG, ids=tuple(_text(entry, "id") for entry in CATALOG))
def test_catalog_entry_names_an_existing_deterministic_killer(
    entry: dict[str, object],
) -> None:
    mechanism = _text(entry, "mechanism")
    evidence = _text(entry, "evidence")
    source, test_name = _evidence_source(entry)

    assert mechanism in ALLOWED_MECHANISMS
    assert _text(entry, "command") == f"{COMMAND_PREFIX} {evidence}"
    assert source.is_file()
    assert source.name.startswith("test_")
    assert test_name.startswith("test_")
    definitions = {
        node.name
        for node in ast.parse(source.read_text(encoding="utf-8"), filename=str(source)).body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert test_name in definitions


@pytest.mark.parametrize("entry", CATALOG, ids=tuple(_text(entry, "id") for entry in CATALOG))
def test_no_catalog_entry_names_deleted_machinery(entry: dict[str, object]) -> None:
    words = f"{_text(entry, 'id')} {_text(entry, 'mutation')}".lower()

    found = [word for word in DELETED_MACHINERY if word in words]

    assert found == []
