"""Commutativity and scale acceptance for generated repositories.

Live timing misses are warned and recorded, never used as flaky assertions.
Set ``RECORD_PERFORMANCE_BUDGETS=1`` when running this test to replace the
committed record with that live result. Ordinary test runs leave it untouched.
Correctness, record shape, and socket isolation remain hard failures.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import cast
import warnings

import instantiate

PROPERTY_ID = "REPOCTL::INDEPENDENT-CAPABILITIES-COMMUTE"
PACK_ROOT = Path(__file__).resolve().parents[2]
PERFORMANCE_RECORD = PACK_ROOT / "tests/fixtures/performance_budgets.json"
PERFORMANCE_PROBE = PACK_ROOT / "tests/scale/performance_probe.py"
RECORD_BUDGETS_ENVIRONMENT_VARIABLE = "RECORD_PERFORMANCE_BUDGETS"
BUDGETS_SECONDS = {
    "status": 0.250,
    "capability_plan": 0.500,
    "capability_apply": 1.000,
    "generate": 1.000,
}


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _run(
    command: list[str],
    *,
    cwd: Path,
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = instantiate.environment_without_local_git_context()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_environment is not None:
        environment.update(extra_environment)
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )


def _read_record(path: Path) -> dict[str, object]:
    document = cast("object", json.loads(path.read_text(encoding="utf-8")))
    return _mapping(document)


def _assert_record_is_complete(record: dict[str, object]) -> None:
    assert record["schema_version"] == 1
    assert record["capability_count"] == 100
    assert record["warm_runs"] == 1
    assert record["samples_per_operation"] == 5
    assert record["network_isolation"] == "pytest-socket --disable-socket"

    environment = _mapping(record["environment"])
    for name in ("machine", "platform", "python_implementation", "python_version"):
        assert isinstance(environment[name], str)
        assert environment[name]

    operations = _mapping(record["operations"])
    assert operations.keys() == BUDGETS_SECONDS.keys()
    regressions = []
    for name, budget in BUDGETS_SECONDS.items():
        result = _mapping(operations[name])
        assert result["budget_seconds"] == budget
        median_seconds = result["median_seconds"]
        within_budget = result["within_budget"]
        assert isinstance(median_seconds, int | float)
        assert median_seconds >= 0
        assert isinstance(within_budget, bool)
        assert within_budget is (median_seconds < budget)
        if not within_budget:
            regressions.append(name)
    assert record["recorded_regressions"] == sorted(regressions)


def test_commutativity_proof_and_scale_record_are_live(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    error = instantiate.generate("scale-proof", "scale_proof", generated)
    assert error is None, error

    report = _run(["just", "proof-report"], cwd=generated)
    assert report.returncode == 0, report.stdout + report.stderr
    assert PROPERTY_ID in report.stdout

    proof = _run(["just", "prove-one", PROPERTY_ID], cwd=generated)
    assert proof.returncode == 0, proof.stdout + proof.stderr

    probe = generated / "verification/repoctl/scale_probe/test_performance_probe.py"
    probe.parent.mkdir()
    _ = shutil.copyfile(PERFORMANCE_PROBE, probe)
    live_record = tmp_path / "live-performance-budgets.json"
    measurement = _run(
        [
            "uv",
            "run",
            "pytest",
            "-q",
            "--disable-socket",
            "-o",
            "addopts=--strict-config --strict-markers",
            str(probe.relative_to(generated)),
        ],
        cwd=generated,
        extra_environment={"PERFORMANCE_RESULT_PATH": os.fspath(live_record)},
    )
    assert measurement.returncode == 0, measurement.stdout + measurement.stderr

    if os.environ.get(RECORD_BUDGETS_ENVIRONMENT_VARIABLE) == "1":
        _ = shutil.copyfile(live_record, PERFORMANCE_RECORD)

    recorded = _read_record(PERFORMANCE_RECORD)
    live = _read_record(live_record)
    _assert_record_is_complete(recorded)
    _assert_record_is_complete(live)
    for field in (
        "schema_version",
        "capability_count",
        "warm_runs",
        "samples_per_operation",
        "network_isolation",
    ):
        assert recorded[field] == live[field]
    recorded_operations = _mapping(recorded["operations"])
    live_operations = _mapping(live["operations"])
    assert {
        name: _mapping(result)["budget_seconds"] for name, result in recorded_operations.items()
    } == {name: _mapping(result)["budget_seconds"] for name, result in live_operations.items()}

    regressions = live["recorded_regressions"]
    assert isinstance(regressions, list)
    if regressions:
        warnings.warn(
            f"100-capability budget misses recorded in {live_record}: {regressions}",
            RuntimeWarning,
            stacklevel=2,
        )
