"""Functional acceptance probes.

Probes are the objective functional yardstick: the same argv sequences run
against both arms, judged only by exit codes and output regexes taken from
the specification the builder received. No shell is involved; state flows
between probes through the shared `{db}` path and explicit captures.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import time

from benchmarks.e2e.config import ProbeSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class ProbeResult:
    name: str
    argv: tuple[str, ...]
    passed: bool
    failure: str | None
    exit_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "argv": list(self.argv),
            "passed": self.passed,
            "failure": self.failure,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _resolve_argv(
    probe: ProbeSpec, variables: dict[str, str]
) -> tuple[tuple[str, ...] | None, str | None]:
    resolved: list[str] = []
    for item in probe.argv:
        try:
            resolved.append(item.format(**variables))
        except (KeyError, IndexError) as error:
            return None, f"unknown placeholder in argv item {item!r}: {error}"
    return tuple(resolved), None


def _decode_partial(data: object) -> str:
    """TimeoutExpired output may be bytes, str, or None depending on capture."""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data if isinstance(data, str) else ""


def _check_output(pattern: str | None, text: str, *, stream: str) -> str | None:
    if pattern is None:
        return None
    if re.search(pattern, text) is None:
        return f"{stream} did not match {pattern!r}"
    return None


type ProbeObserver = Callable[[ProbeResult, int, int], None]


def run_probes(
    probes: tuple[ProbeSpec, ...],
    workspace: Path,
    scratch_dir: Path,
    on_result: ProbeObserver | None = None,
) -> list[ProbeResult]:
    """Run the probe scenario in order inside *workspace*.

    A probe that cannot even resolve its argv still produces a failed result,
    and the scenario continues: later probes may fail for the same root cause,
    but the report then shows the full damage instead of one opaque stop.
    *on_result* observes each result as it lands (index, total), so a live
    front-end can tick the checklist while the scenario is still running.
    """
    scratch_dir.mkdir(parents=True, exist_ok=True)
    variables: dict[str, str] = {
        "db": str(scratch_dir / "probe.db"),
        "ws": str(workspace),
    }
    results: list[ProbeResult] = []
    for index, probe in enumerate(probes):
        result = _run_probe(probe, workspace, variables)
        results.append(result)
        if on_result is not None:
            on_result(result, index, len(probes))
    return results


def _run_probe(probe: ProbeSpec, workspace: Path, variables: dict[str, str]) -> ProbeResult:
    argv, resolve_failure = _resolve_argv(probe, variables)
    if argv is None:
        return ProbeResult(
            name=probe.name,
            argv=probe.argv,
            passed=False,
            failure=resolve_failure,
            exit_code=None,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        )
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=workspace,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=probe.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        partial_out = expired.stdout or b""
        partial_err = expired.stderr or b""
        return ProbeResult(
            name=probe.name,
            argv=argv,
            passed=False,
            failure=f"timed out after {probe.timeout_seconds:g}s",
            exit_code=None,
            duration_seconds=time.monotonic() - started,
            stdout=_decode_partial(partial_out)[-4000:],
            stderr=_decode_partial(partial_err)[-4000:],
        )
    except OSError as error:
        return ProbeResult(
            name=probe.name,
            argv=argv,
            passed=False,
            failure=f"could not execute: {error}",
            exit_code=None,
            duration_seconds=time.monotonic() - started,
            stdout="",
            stderr="",
        )
    duration = time.monotonic() - started

    failures: list[str] = []
    if completed.returncode != probe.expect_exit:
        failures.append(f"exit code {completed.returncode}, expected {probe.expect_exit}")
    for check in (
        _check_output(probe.stdout_regex, completed.stdout, stream="stdout"),
        _check_output(probe.stderr_regex, completed.stderr, stream="stderr"),
    ):
        if check is not None:
            failures.append(check)
    for variable, pattern in probe.capture:
        match = re.search(pattern, completed.stdout)
        if match is None:
            failures.append(f"capture {variable!r}: stdout did not match {pattern!r}")
        else:
            variables[variable] = match.group(1)

    return ProbeResult(
        name=probe.name,
        argv=argv,
        passed=not failures,
        failure="; ".join(failures) or None,
        exit_code=completed.returncode,
        duration_seconds=duration,
        stdout=completed.stdout[-4000:],
        stderr=completed.stderr[-4000:],
    )


def pass_rate(results: list[ProbeResult]) -> float:
    if not results:
        return 0.0
    return sum(1 for result in results if result.passed) / len(results)
