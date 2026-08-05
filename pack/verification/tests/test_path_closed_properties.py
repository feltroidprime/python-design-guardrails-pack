"""Properties and boundary regressions for repository path classification."""

import ast
from collections.abc import Callable
import inspect
from pathlib import Path
from string import ascii_lowercase, digits
from typing import cast
from unicodedata import normalize

from hypothesis import given, strategies as st
import pytest

from scripts import ownership as ownership_facade
from scripts.path_classifier import (
    AbsolutePathError,
    EmptyPathSegmentError,
    OwnershipPathError,
    OwnershipRoot,
    OwnershipZone,
    OwnershipZoneRoots,
    ParentPathError,
    RepositoryPathCandidate,
    UnicodeNormalizationPathError,
    classify_path,
)
from scripts.path_classifier_specifications import classified_path_is_closed
from verification.harness.assertions import assert_falsifies, assert_property

ROOTS = (
    OwnershipZoneRoots(
        name=OwnershipZone("FOUNDATION"),
        roots=(OwnershipRoot(value="scripts"),),
    ),
    OwnershipZoneRoots(
        name=OwnershipZone("PRODUCT"),
        roots=(OwnershipRoot(value="src/example/modules"),),
    ),
    OwnershipZoneRoots(
        name=OwnershipZone("DERIVED"),
        roots=(OwnershipRoot(value="proof/_generated"),),
    ),
    OwnershipZoneRoots(
        name=OwnershipZone("DECLARATION"),
        roots=(OwnershipRoot(value=".repo"),),
    ),
)
SEGMENTS = st.text(alphabet=ascii_lowercase + digits + "_-", min_size=1, max_size=24)


def _root_facts() -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((str(zone.name), tuple(root.value for root in zone.roots)) for zone in ROOTS)


@pytest.mark.proof
@pytest.mark.proves("PACK::PATH-CLOSED")
@given(zone_index=st.integers(min_value=0, max_value=len(ROOTS) - 1), leaf=SEGMENTS)
def test_successful_classification_is_closed(
    zone_index: int,
    leaf: str,
) -> None:
    expected = ROOTS[zone_index]
    candidate = RepositoryPathCandidate(value=f"{expected.roots[0].value}/{leaf}")

    result = classify_path(candidate, ROOTS)

    assert_property(
        condition=classified_path_is_closed(
            candidate.value,
            _root_facts(),
            str(result),
        ),
        property_id="PACK::PATH-CLOSED",
    )
    assert result == expected.name


@pytest.mark.proof
@pytest.mark.falsifies("PACK::PATH-CLOSED")
def test_wrong_zone_is_a_real_path_closure_counterexample() -> None:
    assert_falsifies(
        condition=classified_path_is_closed(
            "scripts/task.py",
            _root_facts(),
            "PRODUCT",
        ),
        property_id="PACK::PATH-CLOSED",
    )


@given(leaf=SEGMENTS)
def test_absolute_paths_raise_a_named_error(leaf: str) -> None:
    with pytest.raises(AbsolutePathError):
        _ = classify_path(RepositoryPathCandidate(value=f"/{leaf}"), ROOTS)


@given(leaf=SEGMENTS)
def test_parent_escapes_raise_a_named_error(leaf: str) -> None:
    with pytest.raises(ParentPathError):
        _ = classify_path(
            RepositoryPathCandidate(value=f"scripts/../{leaf}"),
            ROOTS,
        )


@given(separator_count=st.integers(min_value=2, max_value=8), leaf=SEGMENTS)
def test_empty_segments_raise_a_named_error(
    separator_count: int,
    leaf: str,
) -> None:
    candidate = RepositoryPathCandidate(value=f"scripts{'/' * separator_count}{leaf}")
    with pytest.raises(EmptyPathSegmentError):
        _ = classify_path(candidate, ROOTS)


@given(composed=st.sampled_from(("é", "Å", "ñ", "ü")))
def test_unicode_normalization_variants_raise_a_named_error(composed: str) -> None:
    decomposed = normalize("NFD", composed)
    assert decomposed != composed
    with pytest.raises(UnicodeNormalizationPathError):
        _ = classify_path(
            RepositoryPathCandidate(value=f"scripts/{decomposed}.py"),
            ROOTS,
        )


def test_script_facade_has_no_second_classification_implementation() -> None:
    source = inspect.getsource(ownership_facade)
    tree = ast.parse(source)
    domain_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "scripts.path_classifier"
        for alias in node.names
    }
    classifier = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "classify_path"
    )
    rule_tables = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and ("ROOT" in target.id or "ZONE" in target.id)
    }
    unwrapped_classifier = cast(
        Callable[
            [RepositoryPathCandidate, tuple[OwnershipZoneRoots, ...]],
            OwnershipZone,
        ],
        inspect.unwrap(classify_path),
    )
    domain_source = inspect.getsourcefile(unwrapped_classifier)

    assert "classify_path" in domain_imports
    assert not any(isinstance(node, (ast.If, ast.Match)) for node in ast.walk(classifier))
    assert rule_tables == set()
    assert domain_source is not None
    assert Path(domain_source).name == "path_classifier.py"
    assert Path(domain_source).read_text(encoding="utf-8") != source


def test_named_path_errors_share_one_boundary_type() -> None:
    assert issubclass(AbsolutePathError, OwnershipPathError)
    assert issubclass(ParentPathError, OwnershipPathError)
    assert issubclass(EmptyPathSegmentError, OwnershipPathError)
    assert issubclass(UnicodeNormalizationPathError, OwnershipPathError)
