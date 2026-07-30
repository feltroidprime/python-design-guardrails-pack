"""Detached-process contract evidence for every repository-control command."""

import json
from pathlib import Path
import subprocess
from typing import cast

import pytest

from repoctl.modules.repository_generation.api import COMMAND_CATALOG, ControlCommandName
from tests.repoctl.contract import cli_process_cases
from tests.repoctl.contract.cli_process_cases import (
    CONTROL_PROCESS_CASES,
    ProcessCase,
    assert_process_cases_cover_control_catalog,
    process_case_command_names,
    run_process_case,
)


def _document(raw: str) -> dict[str, object]:
    value = cast("object", json.loads(raw))
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _assert_machine_stream(raw: str) -> None:
    """Reject diagnostics that would make a protocol stream unsafe to automate."""
    assert "Traceback" not in raw
    assert "\x1b[" not in raw


@pytest.mark.contract
def test_process_case_catalog_covers_every_control_plane_command() -> None:
    assert process_case_command_names() == {
        ControlCommandName.CAPABILITIES,
        ControlCommandName.STATUS,
        ControlCommandName.CAPABILITY_PLAN,
        ControlCommandName.CAPABILITY_APPLY,
    }
    assert {spec.name for spec in COMMAND_CATALOG} == process_case_command_names()
    assert_process_cases_cover_control_catalog()


@pytest.mark.contract
@pytest.mark.parametrize(
    "case",
    CONTROL_PROCESS_CASES,
    ids=tuple(case.identifier for case in CONTROL_PROCESS_CASES),
)
def test_each_control_command_obeys_its_detached_process_contract(
    case: ProcessCase,
    tmp_path: Path,
) -> None:
    result = run_process_case(case, tmp_path)

    assert result.returncode == case.exit_code, result.stdout + result.stderr
    _assert_machine_stream(result.stdout)
    _assert_machine_stream(result.stderr)
    if case.success:
        assert result.stderr == ""
        document = _document(result.stdout)
        assert set(document) == {"schema_version", "command", "data", "metadata"}
        assert document["schema_version"] == "1.0"
        assert document["command"] == case.command
    else:
        assert result.stdout == ""
        document = _document(result.stderr)
        assert set(document) == {"schema_version", "command", "error"}
        assert document["schema_version"] == "1.0"
        assert document["command"] == case.command
        error = _mapping(document["error"])
        assert set(error) == {"code", "message", "retryable", "hint", "details"}
        assert error["code"] == case.error_code
        assert isinstance(error["retryable"], bool)
        assert isinstance(error["hint"], str)
        assert error["hint"]

    case.assert_document(document)


@pytest.mark.contract
def test_detached_runner_closes_stdin_for_every_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(args=("repoctl",), returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr("tests.repoctl.contract.cli_process_cases.subprocess.run", fake_run)

    _ = cli_process_cases.run_repoctl(("capabilities",), cwd=tmp_path)

    assert observed["stdin"] is subprocess.DEVNULL
    assert observed["capture_output"] is True
    assert observed["check"] is False
