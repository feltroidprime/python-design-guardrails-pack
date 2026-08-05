"""Audit the SPEC-0001 mutation catalog without duplicating its test suite."""

import ast
import json
from pathlib import Path
from typing import cast

import pytest

PACK_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = PACK_ROOT / "tests/fixtures/mutation_catalog.json"
ALLOWED_MECHANISMS = frozenset(
    {
        "contract_test",
        "crosshair",
        "guard",
        "hypothesis_property",
        "proof_gate",
    }
)
EXPECTED_MUTATIONS = (
    (1, "planner-absolute-path", "planner emits an absolute path"),
    (2, "planner-parent-traversal", "planner emits ../"),
    (3, "apply-product-overwrite", "apply overwrites an existing PRODUCT file"),
    (4, "apply-stale-digest", "apply ignores a stale digest"),
    (5, "apply-duplicate-declaration", "apply duplicates one declaration"),
    (6, "derived-omit-active", "derived compiler omits an active capability"),
    (7, "derived-include-retired", "derived compiler includes a retired capability"),
    (
        8,
        "activation-missing-proof-evidence",
        "activation ignores missing proof evidence",
    ),
    (9, "retirement-delete-product", "retirement deletes product code"),
    (
        10,
        "nondeterministic-plan-id",
        "identical intents produce different plan IDs",
    ),
    (
        11,
        "cross-capability-internal-import",
        "capability A imports capability B internals",
    ),
    (
        12,
        "cli-command-without-process-case",
        "a CLI command exists without an independent process case",
    ),
    (13, "oracle-always-true", "an oracle returns True"),
    (
        14,
        "pure-target-without-crosshair",
        "a pure target is removed from CrossHair coverage",
    ),
)


def _load_catalog() -> tuple[dict[str, object], ...]:
    document = cast("object", json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
    assert isinstance(document, dict)
    assert document.get("schema_version") == 1
    mutations = document.get("mutations")
    assert isinstance(mutations, list)
    assert all(isinstance(entry, dict) for entry in mutations)
    return tuple(cast("dict[str, object]", entry) for entry in mutations)


def _text(entry: dict[str, object], key: str) -> str:
    value = entry.get(key)
    assert isinstance(value, str)
    assert value
    return value


def _evidence_source(entry: dict[str, object]) -> tuple[Path, str]:
    evidence = _text(entry, "evidence")
    relative, separator, test_name = evidence.partition("::")
    assert separator
    context = _text(entry, "context")
    assert context in {"generated_repository", "pack"}
    root = PACK_ROOT / "template" if context == "generated_repository" else PACK_ROOT
    return root / relative, test_name


def _expected_command(entry: dict[str, object]) -> str:
    evidence = _text(entry, "evidence")
    if _text(entry, "context") == "generated_repository":
        return (
            "HYPOTHESIS_PROFILE=fast uv run pytest -q "
            '-o "addopts=--strict-config --strict-markers --disable-socket" '
            f"{evidence}"
        )
    return (
        "uv run --no-project --python 3.14 --with pytest==9.1.1 "
        '--with copier==9.17.0 --with "icontract>=2.7.3" '
        f"pytest -q {evidence}"
    )


CATALOG = _load_catalog()


def test_catalog_matches_the_fourteen_specification_mutations() -> None:
    observed = tuple(
        (
            entry.get("spec_number"),
            _text(entry, "id"),
            _text(entry, "mutation"),
        )
        for entry in CATALOG
    )

    assert observed == EXPECTED_MUTATIONS


@pytest.mark.parametrize("entry", CATALOG, ids=tuple(_text(entry, "id") for entry in CATALOG))
def test_catalog_entry_names_an_existing_deterministic_killer(
    entry: dict[str, object],
) -> None:
    mechanism = _text(entry, "mechanism")
    command = _text(entry, "command")
    source, test_name = _evidence_source(entry)

    assert mechanism in ALLOWED_MECHANISMS
    assert command == _expected_command(entry)
    assert source.is_file()
    assert source.name.startswith("test_")
    assert test_name.startswith("test_")
    definitions = {
        node.name
        for node in ast.parse(source.read_text(encoding="utf-8"), filename=str(source)).body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert test_name in definitions
