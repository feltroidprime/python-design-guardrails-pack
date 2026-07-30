"""Record the 100-capability command budgets with network access disabled.

Budget misses are written in ``recorded_regressions`` for the caller to report.
They never fail this test: only correctness, socket isolation, and record
integrity do.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from io import StringIO
import json
import os
from pathlib import Path
import platform
import shutil
import socket
from statistics import median
from time import perf_counter_ns
from typing import cast

import pytest
from pytest_socket import SocketBlockedError

from repoctl.modules.repository_generation.adapters.outbound.local_repository import (
    LocalRepository,
)
from repoctl.modules.repository_generation.api import run

CAPABILITY_COUNT = 100
PACKAGE = "scale_project"
SAMPLES = 5
WARM_RUNS = 1
NANOSECONDS_PER_SECOND = 1_000_000_000
BUDGETS_SECONDS = {
    "status": 0.250,
    "capability_plan": 0.500,
    "capability_apply": 1.000,
    "generate": 1.000,
}
COPY_IGNORE = shutil.ignore_patterns(
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
)


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _command(root: Path, *arguments: str) -> dict[str, object]:
    out = StringIO()
    err = StringIO()
    exit_code = run(
        arguments,
        repository=LocalRepository(root=root, package=PACKAGE),
        out=out,
        err=err,
    )
    assert exit_code == 0, err.getvalue()
    assert err.getvalue() == ""
    document = cast("object", json.loads(out.getvalue()))
    return _mapping(document)


def _plan(root: Path, name: str) -> str:
    destination = f".repo/plans/{name}.json"
    _ = _command(
        root,
        "capability",
        "plan",
        name,
        "--inbound",
        "python",
        "--output",
        destination,
    )
    return destination


def _plan_and_apply(root: Path, name: str) -> None:
    destination = _plan(root, name)
    document = _command(root, "capability", "apply", destination)
    data = _mapping(document["data"])
    assert data["status"] == "applied"


def _build_capabilities(root: Path) -> None:
    for index in range(CAPABILITY_COUNT):
        _plan_and_apply(root, f"scale_{index:03d}")
    status = _mapping(_command(root, "status")["data"])
    counts = _mapping(status["capability_counts"])
    assert counts == {"active": 0, "draft": CAPABILITY_COUNT, "retired": 0}


def _median_seconds(operation: Callable[[], object]) -> float:
    _ = operation()
    durations = []
    for _index in range(SAMPLES):
        started = perf_counter_ns()
        _ = operation()
        durations.append((perf_counter_ns() - started) / NANOSECONDS_PER_SECOND)
    return median(durations)


def _apply_median_seconds(root: Path, sample_root: Path) -> float:
    durations = []
    for index in range(WARM_RUNS + SAMPLES):
        repository = sample_root / f"apply-{index}"
        _ = shutil.copytree(root, repository, ignore=COPY_IGNORE)
        destination = _plan(repository, f"measured_apply_{index}")
        started = perf_counter_ns()
        document = _command(repository, "capability", "apply", destination)
        duration = (perf_counter_ns() - started) / NANOSECONDS_PER_SECOND
        assert _mapping(document["data"])["status"] == "applied"
        if index >= WARM_RUNS:
            durations.append(duration)
    return median(durations)


def _plan_median_seconds(root: Path) -> float:
    durations = []
    for index in range(WARM_RUNS + SAMPLES):
        started = perf_counter_ns()
        _ = _plan(root, f"measured_plan_{index}")
        duration = (perf_counter_ns() - started) / NANOSECONDS_PER_SECOND
        if index >= WARM_RUNS:
            durations.append(duration)
    return median(durations)


def _operation_record(median_seconds: float, budget_seconds: float) -> dict[str, object]:
    return {
        "median_seconds": round(median_seconds, 6),
        "budget_seconds": budget_seconds,
        "within_budget": median_seconds < budget_seconds,
    }


def _write_record(root: Path, sample_root: Path) -> dict[str, object]:
    medians = {
        "status": _median_seconds(lambda: _command(root, "status")),
        "capability_plan": _plan_median_seconds(root),
        "capability_apply": _apply_median_seconds(root, sample_root),
        "generate": _median_seconds(lambda: _command(root, "generate")),
    }
    operations = {
        name: _operation_record(medians[name], budget) for name, budget in BUDGETS_SECONDS.items()
    }
    regressions = sorted(
        name for name, result in operations.items() if not cast("bool", result["within_budget"])
    )
    return {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "environment": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
        },
        "capability_count": CAPABILITY_COUNT,
        "warm_runs": WARM_RUNS,
        "samples_per_operation": SAMPLES,
        "network_isolation": "pytest-socket --disable-socket",
        "operations": operations,
        "recorded_regressions": regressions,
    }


def test_measure_one_hundred_capability_command_budgets(
    tmp_path: Path,
) -> None:
    with pytest.raises(SocketBlockedError):
        _ = socket.socket()

    root = Path.cwd()
    _build_capabilities(root)
    record = _write_record(root, tmp_path)
    output = Path(os.environ["PERFORMANCE_RESULT_PATH"])
    _ = output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    assert isinstance(record["recorded_regressions"], list)
