"""Independent assertions for the private session-evidence bundle contract."""

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.agent_sessions import AgentType

EXPECTED_CHECKS = {
    "content_hashes",
    "coverage",
    "metric_coherence",
    "no_orphan_blob_references",
    "profile_rows",
    "subagent_references",
}
EXPECTED_OUTPUT = {
    "blobs",
    "manifest.json",
    "profile.tsv",
    "route.txt",
    "trajectory.atif.json",
}


def mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def document(path: Path) -> dict[str, object]:
    return mapping(cast("object", json.loads(path.read_text(encoding="utf-8"))))


def assert_valid_bundle(output: Path, *, agent_type: AgentType) -> dict[str, object]:
    """Pin the complete self-check vocabulary and public artifact shape."""
    manifest = document(output / "manifest.json")
    checks = mapping(manifest["checks"])
    trajectory = document(output / "trajectory.atif.json")

    assert {path.name for path in output.iterdir()} == EXPECTED_OUTPUT
    assert manifest["agent_type"] == agent_type
    assert manifest["valid"] is True
    assert set(checks) == EXPECTED_CHECKS
    assert all(value is True for value in checks.values())
    assert trajectory["schema_version"] == "ATIF-v1.7"
    return manifest
