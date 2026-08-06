"""Prove this repository composes its opt-in private session tool."""

import json
from typing import TYPE_CHECKING, cast

import pytest

from scripts.agent_sessions import convert_session
from tests.e2e.session_contract import assert_valid_bundle, document, mapping

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.session_e2e


def test_private_session_profiler_dependency_converts_through_facade(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "rollout.jsonl"
    first_output = tmp_path / "first-output"
    second_output = tmp_path / "second-output"
    events = [
        {
            "timestamp": "2026-07-16T12:00:00Z",
            "type": "session_meta",
            "payload": {"id": "generated-repository-proof", "cli_version": "test"},
        },
        {
            "timestamp": "2026-07-16T12:00:00.100Z",
            "type": "event_msg",
            "payload": {"type": "task_started"},
        },
    ]
    _ = transcript.write_text(
        "".join(f"{json.dumps(event, separators=(',', ':'))}\n" for event in events),
        encoding="utf-8",
    )

    _ = convert_session(transcript, first_output)
    _ = convert_session(transcript, second_output)

    manifest = assert_valid_bundle(first_output, agent_type="codex")
    assert manifest["harbor_version"] == "0.18.0"
    raw_sources = cast("list[object]", manifest["raw_sources"])
    source = mapping(raw_sources[0])
    content_ref = cast("str", source["content_ref"])
    assert (first_output / content_ref).read_bytes() == transcript.read_bytes()
    assert {
        path.relative_to(first_output): path.read_bytes()
        for path in first_output.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(second_output): path.read_bytes()
        for path in second_output.rglob("*")
        if path.is_file()
    }
    assert document(first_output / "manifest.json") == document(second_output / "manifest.json")
