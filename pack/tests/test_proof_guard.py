"""Fault-injection tests for the closed proof chain and its catalog.

Each test plants one defect in the tree of `tests.proof_tree` and states the
code the guard must report. This module covers the complete chain, catalog
loading, the declared targets, and the exemption clock. The evidence rules,
the oracle rules and the callable targets each have their own module.
"""

from pathlib import Path

import pytest

from scripts.proof_catalog import (
    CatalogError,
    DuplicatePropertyIdError,
    load_catalog,
)
from scripts.proof_guard import check
from tests.proof_tree import (
    CAPABILITY_TOML,
    DECISION,
    EVIDENCE,
    POLICY_TOML,
    PROOF_TOML,
    SPECIFICATION,
    foundation_catalog,
    proof_project,
    proof_root,
    violation_codes,
    write_policy,
)


def test_complete_property_chain_passes(tmp_path: Path) -> None:
    root = proof_project(tmp_path)

    catalog, violations = check(root)

    assert catalog is not None
    assert violations == ()
    assert catalog.index.as_dict() == {
        "schema_version": 1,
        "catalogs": [
            {
                "path": "pack/proof/foundation.toml",
                "property_ids": ["DEMO-PRESERVES-VALUE"],
                "exemption_targets": [],
            },
            {
                "path": "src/demo/feature/proof.toml",
                "property_ids": [],
                "exemption_targets": [],
            },
        ],
    }


def test_namespaced_property_id_closes_a_complete_chain(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    namespaced_id = "REPOCTL::DEMO-PRESERVES-VALUE"
    paths = (
        foundation_catalog(root),
        root / "src/demo/feature/domain/decisions.py",
        root / "verification/tests/test_properties.py",
    )
    for path in paths:
        _ = path.write_text(
            path.read_text(encoding="utf-8").replace(
                "DEMO-PRESERVES-VALUE",
                namespaced_id,
            ),
            encoding="utf-8",
        )

    catalog, violations = check(root)

    assert violations == ()
    assert catalog is not None
    assert catalog.properties[0].property_id == namespaced_id


def test_public_facade_reexports_resolve_to_exact_proof_symbols(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    _ = (root / "src/demo/feature/api.py").write_text(
        """from demo.feature.domain.decisions import identity
from demo.feature.domain.specifications import identity_matches

__all__ = ["identity", "identity_matches"]
""",
        encoding="utf-8",
    )
    evidence = EVIDENCE.replace(
        """from demo.feature.domain.decisions import identity
from demo.feature.domain.specifications import identity_matches""",
        "from demo.feature.api import identity, identity_matches",
    )
    _ = (root / "verification/tests/test_properties.py").write_text(
        evidence,
        encoding="utf-8",
    )

    catalog, violations = check(root)

    assert violations == ()
    assert catalog is not None


def test_loader_rejects_duplicate_property_id_across_catalogs(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    duplicate = proof_root(root) / "extra/duplicate.toml"
    duplicate.parent.mkdir()
    _ = duplicate.write_text(PROOF_TOML, encoding="utf-8")

    with pytest.raises(DuplicatePropertyIdError, match="Duplicate property IDs across catalogs"):
        _ = load_catalog(root)


def test_loader_discovers_every_catalog_below_the_proof_root(tmp_path: Path) -> None:
    """Discovery is structural, so the policy declares no catalog root."""
    root = proof_project(tmp_path)
    nested = proof_root(root) / "extra/nested.toml"
    nested.parent.mkdir()
    _ = nested.write_text(CAPABILITY_TOML, encoding="utf-8")

    catalog = load_catalog(root)

    assert [entry.path.name for entry in catalog.catalogs] == [
        "nested.toml",
        "foundation.toml",
        "proof.toml",
    ]


def test_loader_rejects_a_capability_without_a_proof_catalog(tmp_path: Path) -> None:
    """AGENTS.md gives every capability one `proof.toml`."""
    root = proof_project(tmp_path)
    (root / "src/demo/feature/proof.toml").unlink()

    with pytest.raises(CatalogError, match=r"Capability without proof\.toml: feature"):
        _ = load_catalog(root)


def test_one_policy_discovers_a_behavior_root_beside_the_domain(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    write_policy(
        root,
        POLICY_TOML.replace('behavior_roots = ["domain"]', 'behavior_roots = ["outside"]'),
    )
    _ = foundation_catalog(root).write_text(
        PROOF_TOML.replace("demo.feature.domain", "demo.feature.outside"),
        encoding="utf-8",
    )
    (root / "src/demo/feature/outside").mkdir()
    _ = (root / "src/demo/feature/outside/specifications.py").write_text(
        SPECIFICATION, encoding="utf-8"
    )
    _ = (root / "src/demo/feature/outside/decisions.py").write_text(
        DECISION.replace("demo.feature.domain", "demo.feature.outside"),
        encoding="utf-8",
    )
    _ = (root / "verification/tests/test_properties.py").write_text(
        EVIDENCE.replace("demo.feature.domain", "demo.feature.outside"),
        encoding="utf-8",
    )

    catalog, violations = check(root)

    assert violations == ()
    assert catalog is not None
    property_spec = catalog.by_id["DEMO-PRESERVES-VALUE"]
    assert property_spec.targets == ("demo.feature.outside.decisions:identity",)
    assert property_spec.evidence == frozenset(
        {"icontract", "hypothesis", "crosshair", "falsifier"}
    )


def test_new_public_core_behavior_is_rejected_until_classified(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decisions = root / "src/demo/feature/domain/decisions.py"
    source = decisions.read_text(encoding="utf-8")
    _ = decisions.write_text(
        f"{source}\n\ndef unclassified(value: int) -> int:\n    return value\n",
        encoding="utf-8",
    )

    assert "PROOF001" in violation_codes(root)


def test_property_target_without_linked_icontract_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    decision = root / "src/demo/feature/domain/decisions.py"
    _ = decision.write_text(
        "def identity(value: int) -> int:\n    return value\n",
        encoding="utf-8",
    )

    codes = violation_codes(root)

    assert "PROOF006" in codes
    assert "PROOF009" in codes


def test_top_level_function_target_remains_recognized(tmp_path: Path) -> None:
    root = proof_project(tmp_path)

    assert violation_codes(root) == set()


def test_missing_declared_target_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    manifest = foundation_catalog(root)
    _ = manifest.write_text(
        PROOF_TOML.replace(
            "demo.feature.domain.decisions:identity",
            "demo.feature.domain.decisions:missing_identity",
        ),
        encoding="utf-8",
    )

    assert "PROOF005" in violation_codes(root)


def test_missing_declared_oracle_is_rejected(tmp_path: Path) -> None:
    root = proof_project(tmp_path)
    manifest = foundation_catalog(root)
    _ = manifest.write_text(
        PROOF_TOML.replace(
            "demo.feature.domain.specifications:identity_matches",
            "demo.feature.domain.specifications:missing_identity_matches",
        ),
        encoding="utf-8",
    )

    assert "PROOF008" in violation_codes(root)


def test_blank_scope_or_counterexample_is_rejected_by_the_catalog(
    tmp_path: Path,
) -> None:
    root = proof_project(tmp_path)
    manifest = foundation_catalog(root)
    _ = manifest.write_text(
        PROOF_TOML.replace(
            'scope = "The synchronous identity decision."',
            'scope = " "',
        ),
        encoding="utf-8",
    )

    assert "PROOF000" in violation_codes(root)


EXEMPTED_BEHAVIOR = "\n\ndef unclassified(value: int) -> int:\n    return value\n"


def exempting_project(tmp_path: Path, revisit: str) -> Path:
    root = proof_project(tmp_path)
    decisions = root / "src/demo/feature/domain/decisions.py"
    _ = decisions.write_text(
        decisions.read_text(encoding="utf-8") + EXEMPTED_BEHAVIOR,
        encoding="utf-8",
    )
    _ = foundation_catalog(root).write_text(
        PROOF_TOML
        + f'''
[[exemptions]]
target = "demo.feature.domain.decisions:unclassified"
reason = "Scheduled for a property once the shape settles."
revisit = "{revisit}"
''',
        encoding="utf-8",
    )
    return root


def test_unexpired_exemption_closes_the_surface(tmp_path: Path) -> None:
    root = exempting_project(tmp_path, "2099-01-01")

    _, violations = check(root)

    assert violations == ()


def test_expired_exemption_reopens_the_surface(tmp_path: Path) -> None:
    root = exempting_project(tmp_path, "2000-01-01")

    _, violations = check(root)

    assert [violation.code for violation in violations] == ["PROOF000"]
    assert "expired on 2000-01-01" in violations[0].message
