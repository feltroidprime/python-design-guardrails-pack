"""Neutral quantitative metrics, applied identically to both arms.

Neutrality rules:

- analyzers run at pinned versions through `uvx`, never through either arm's
  own toolchain, and with fixed flags (`ruff --isolated`, a generated
  basedpyright config), so neither arm's local configuration can soften or
  harden its own measurement;
- each arm's *own* test suite runs with the arm's own configuration — that
  result measures the arm's self-imposed standard, and is reported as such;
- every raw analyzer output is written next to the summary so any number in
  the report can be audited.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import time

from benchmarks.e2e.config import RunSettings, ToolPins, matches_exclude

_EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".import_linter_cache",
    "node_modules",
    "build",
    "dist",
    "htmlcov",
}

_TEST_DIR_NAMES = {"tests", "test"}


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandRecord:
    """One executed measurement command, kept for auditability."""

    argv: tuple[str, ...]
    exit_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    timed_out: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "timed_out": self.timed_out,
        }


def _run(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    timeout: float,
    env: dict[str, str] | None = None,
) -> CommandRecord:
    merged_env = {**os.environ, **(env or {})}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            env=merged_env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CommandRecord(
            argv=argv,
            exit_code=None,
            duration_seconds=time.monotonic() - started,
            stdout="",
            stderr="",
            timed_out=True,
        )
    except OSError as error:
        return CommandRecord(
            argv=argv,
            exit_code=None,
            duration_seconds=time.monotonic() - started,
            stdout="",
            stderr=str(error),
        )
    return CommandRecord(
        argv=argv,
        exit_code=completed.returncode,
        duration_seconds=time.monotonic() - started,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _is_excluded(path: Path, root: Path) -> bool:
    return any(part in _EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts)


def is_test_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in _TEST_DIR_NAMES for part in relative.parts[:-1]):
        return True
    return (
        relative.name.startswith("test_")
        or relative.name.endswith("_test.py")
        or relative.name == "conftest.py"
    )


def python_files(
    root: Path, app_exclude: tuple[str, ...] = ()
) -> tuple[list[Path], list[Path]]:
    """Return (source files, test files), excluding derived artifacts.

    *app_exclude* applies the same symmetric application-deliverable scope as
    the judge bundle and coverage, so every static metric counts the same
    files the qualitative comparison is about — not repository infrastructure.
    """
    sources: list[Path] = []
    tests: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if _is_excluded(path, root):
            continue
        if matches_exclude(path.relative_to(root).as_posix(), app_exclude):
            continue
        (tests if is_test_file(path, root) else sources).append(path)
    return sources, tests


def _loc(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += sum(1 for line in content.splitlines() if line.strip())
    return total


def loc_summary(root: Path, app_exclude: tuple[str, ...] = ()) -> dict[str, object]:
    sources, tests = python_files(root, app_exclude)
    return {
        "source_files": len(sources),
        "source_loc": _loc(sources),
        "test_files": len(tests),
        "test_loc": _loc(tests),
    }


def per_kloc(count: int, loc: int) -> float | None:
    if loc <= 0:
        return None
    return round(count / (loc / 1000), 2)


def parse_ruff_output(stdout: str) -> dict[str, object]:
    try:
        entries = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return {"violations": None, "by_code": {}, "parse_error": True}
    if not isinstance(entries, list):
        return {"violations": None, "by_code": {}, "parse_error": True}
    by_code: dict[str, int] = {}
    for entry in entries:
        if isinstance(entry, dict):
            code = entry.get("code")
            if isinstance(code, str):
                by_code[code] = by_code.get(code, 0) + 1
    return {
        "violations": len(entries),
        "by_code": dict(sorted(by_code.items(), key=lambda item: (-item[1], item[0]))),
        "parse_error": False,
    }


def parse_basedpyright_output(stdout: str) -> dict[str, object]:
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return {"errors": None, "warnings": None, "parse_error": True}
    summary = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return {"errors": None, "warnings": None, "parse_error": True}
    return {
        "errors": summary.get("errorCount"),
        "warnings": summary.get("warningCount"),
        "files_analyzed": summary.get("filesAnalyzed"),
        "parse_error": False,
    }


def parse_radon_cc_output(stdout: str) -> dict[str, object]:
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return {"blocks": None, "average_complexity": None, "max_complexity": None,
                "parse_error": True}
    complexities: list[int] = []
    if isinstance(data, dict):
        for blocks in data.values():
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if isinstance(block, dict) and isinstance(block.get("complexity"), int):
                    complexities.append(block["complexity"])
    if not complexities:
        return {"blocks": 0, "average_complexity": None, "max_complexity": None,
                "parse_error": False}
    return {
        "blocks": len(complexities),
        "average_complexity": round(sum(complexities) / len(complexities), 2),
        "max_complexity": max(complexities),
        "parse_error": False,
    }


def parse_coverage_json(
    text: str, root: Path, app_exclude: tuple[str, ...] = ()
) -> dict[str, object]:
    """Aggregate in-process line coverage over non-test application files.

    *app_exclude* is the same symmetric pattern list the judge uses, so
    repository infrastructure (guard scripts, docs tooling) neither inflates
    nor dilutes the application figure in either arm. Coverage is measured
    in-process: an arm whose tests exercise the program only through
    subprocesses will legitimately measure near zero here — the report labels
    the metric accordingly.
    """
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {"percent": None, "measured_files": 0, "parse_error": True}
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return {"percent": None, "measured_files": 0, "parse_error": True}
    covered = 0
    statements = 0
    measured = 0
    for name, entry in files.items():
        path = Path(name)
        if not path.is_absolute():
            path = root / path
        try:
            relative = path.relative_to(root)
            if (
                _is_excluded(path, root)
                or is_test_file(path, root)
                or matches_exclude(relative.as_posix(), app_exclude)
            ):
                continue
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        summary = entry.get("summary")
        if not isinstance(summary, dict):
            continue
        covered += int(summary.get("covered_lines", 0))
        statements += int(summary.get("num_statements", 0))
        measured += 1
    if statements == 0:
        return {"percent": None, "measured_files": measured, "parse_error": False}
    return {
        "percent": round(100 * covered / statements, 1),
        "measured_files": measured,
        "parse_error": False,
    }


_PYTEST_COUNTER = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


def parse_pytest_summary(stdout: str) -> dict[str, int]:
    """Extract counters from the LAST pytest summary line only.

    Candidate test suites may themselves print pytest-like output (e.g. tests
    driving a CLI through subprocesses); scanning the whole stdout would
    double-count those. The real summary is the last matching line.
    """
    for line in reversed(stdout.splitlines()):
        matches = list(_PYTEST_COUNTER.finditer(line))
        if matches:
            counts: dict[str, int] = {}
            for match in matches:
                word = match.group(2)
                key = word.rstrip("s") if word.startswith("error") else word
                counts[key] = counts.get(key, 0) + int(match.group(1))
            return counts
    return {}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Pyright resolves include/exclude patterns relative to the config file's
# directory, so the neutral config must live at the workspace root for the
# excludes to bite. It is restored/removed afterwards; a copy stays in the
# metrics directory for audit. pyrightconfig.json also outranks any
# [tool.basedpyright]/[tool.pyright] table, which is exactly what makes the
# measurement identical for both arms.
_BASEDPYRIGHT_NEUTRAL_CONFIG = {
    "include": ["."],
    "exclude": [
        "**/.venv",
        "**/__pycache__",
        "**/.git",
        "**/node_modules",
        "**/build",
        "**/dist",
    ],
    "typeCheckingMode": "standard",
    "pythonVersion": "3.14",
    "venvPath": ".",
    "venv": ".venv",
}


def _run_basedpyright(
    workspace: Path,
    out_dir: Path,
    *,
    pins: ToolPins,
    timeout: float,
    app_exclude: tuple[str, ...] = (),
) -> CommandRecord:
    scope_excludes: list[str] = []
    for pattern in app_exclude:
        scope_excludes.append(pattern)
        bare = pattern.rstrip("/*")
        if bare and bare != pattern:
            scope_excludes.append(bare)
    config = {
        **_BASEDPYRIGHT_NEUTRAL_CONFIG,
        "exclude": [*_BASEDPYRIGHT_NEUTRAL_CONFIG["exclude"], *scope_excludes],
    }
    content = json.dumps(config, indent=2)
    _write(out_dir / "basedpyright.config.json", content)
    config_path = workspace / "pyrightconfig.json"
    original = config_path.read_text(encoding="utf-8") if config_path.is_file() else None
    config_path.write_text(content, encoding="utf-8")
    try:
        return _run(
            (
                "uvx",
                f"basedpyright@{pins.basedpyright}",
                "--outputjson",
                "--project",
                str(config_path),
            ),
            cwd=workspace,
            timeout=timeout,
        )
    finally:
        if original is None:
            config_path.unlink(missing_ok=True)
        else:
            config_path.write_text(original, encoding="utf-8")


def collect_metrics(
    workspace: Path,
    out_dir: Path,
    *,
    pins: ToolPins,
    run: RunSettings,
    app_exclude: tuple[str, ...] = (),
) -> dict[str, object]:
    """Measure one arm's workspace; write raw outputs under *out_dir*.

    All static metrics use the application scope (*app_exclude*, the same
    symmetric list the judge bundle uses); `loc_repo` additionally records the
    unscoped repository size as a descriptive figure.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, CommandRecord] = {}
    scoped_loc = loc_summary(workspace, app_exclude)
    summary: dict[str, object] = {"loc": scoped_loc, "loc_repo": loc_summary(workspace)}
    app_loc = int(scoped_loc["source_loc"]) + int(scoped_loc["test_loc"])  # type: ignore[call-overload]

    install = _run(
        ("uv", "sync", "--all-groups"),
        cwd=workspace,
        timeout=run.install_timeout_seconds,
    )
    records["install"] = install
    summary["install"] = {
        "succeeded": install.exit_code == 0,
        "duration_seconds": round(install.duration_seconds, 1),
    }

    own_tests = _run(
        ("uv", "run", "pytest", "-q"),
        cwd=workspace,
        timeout=run.tests_timeout_seconds,
    )
    records["own_tests"] = own_tests
    summary["own_tests"] = {
        "exit_code": own_tests.exit_code,
        "timed_out": own_tests.timed_out,
        "counts": parse_pytest_summary(own_tests.stdout),
        "duration_seconds": round(own_tests.duration_seconds, 1),
    }

    coverage_data = out_dir / "coverage.data"
    # A generated rcfile is the ONLY coverage config in play: it prevents an
    # arm's own [tool.coverage] settings (exclude_also, omit, fail_under)
    # from softening or failing its "neutral" number. PYTHONPATH puts local
    # sources ahead of the installed copy in .venv/site-packages so
    # `source=.` measures the files the repository actually contains, and
    # addopts are neutralized to keep any arm-specific pytest coverage plugin
    # from fighting the outer trace. Identical for both arms.
    coverage_rc = out_dir / "coverage.neutral.cfg"
    _write(coverage_rc, "[run]\nbranch = True\nsource = .\n")
    coverage_env = {
        "COVERAGE_FILE": str(coverage_data),
        "PYTHONPATH": os.pathsep.join(("src", ".")),
    }
    coverage_run = _run(
        (
            "uv",
            "run",
            "--with",
            f"coverage=={pins.coverage}",
            "coverage",
            "run",
            f"--rcfile={coverage_rc}",
            "-m",
            "pytest",
            "-q",
            "--override-ini=addopts=",
        ),
        cwd=workspace,
        timeout=run.tests_timeout_seconds,
        env=coverage_env,
    )
    records["coverage_run"] = coverage_run
    coverage_json_path = out_dir / "coverage.json"
    coverage_report = _run(
        (
            "uv",
            "run",
            "--with",
            f"coverage=={pins.coverage}",
            "coverage",
            "json",
            f"--rcfile={coverage_rc}",
            "-o",
            str(coverage_json_path),
        ),
        cwd=workspace,
        timeout=run.tests_timeout_seconds,
        env={"COVERAGE_FILE": str(coverage_data)},
    )
    records["coverage_report"] = coverage_report
    coverage_text = (
        coverage_json_path.read_text(encoding="utf-8") if coverage_json_path.is_file() else ""
    )
    coverage_summary = parse_coverage_json(coverage_text, workspace, app_exclude)
    coverage_summary["run_exit_code"] = coverage_run.exit_code
    coverage_summary["report_exit_code"] = coverage_report.exit_code
    summary["coverage"] = coverage_summary

    sources, tests = python_files(workspace, app_exclude)
    scoped_files = [*sources, *tests]
    if scoped_files:
        ruff = _run(
            (
                "uvx",
                f"ruff@{pins.ruff}",
                "check",
                "--isolated",
                "--select",
                pins.ruff_select,
                "--ignore",
                pins.ruff_ignore,
                "--output-format",
                "json",
                "--exit-zero",
                *[str(path) for path in scoped_files],
            ),
            cwd=workspace,
            timeout=run.install_timeout_seconds,
        )
        records["ruff"] = ruff
        ruff_summary = parse_ruff_output(ruff.stdout)
    else:
        ruff_summary = {"violations": 0, "by_code": {}, "parse_error": False}
    violations = ruff_summary.get("violations")
    ruff_summary["per_kloc"] = (
        per_kloc(violations, app_loc) if isinstance(violations, int) else None
    )
    summary["ruff"] = ruff_summary

    basedpyright = _run_basedpyright(
        workspace,
        out_dir,
        pins=pins,
        timeout=run.install_timeout_seconds,
        app_exclude=app_exclude,
    )
    records["basedpyright"] = basedpyright
    pyright_summary = parse_basedpyright_output(basedpyright.stdout)
    errors = pyright_summary.get("errors")
    pyright_summary["errors_per_kloc"] = (
        per_kloc(errors, app_loc) if isinstance(errors, int) else None
    )
    summary["basedpyright"] = pyright_summary

    if sources:
        radon = _run(
            ("uvx", f"radon@{pins.radon}", "cc", "-j", *[str(path) for path in sources]),
            cwd=workspace,
            timeout=run.install_timeout_seconds,
        )
        records["radon"] = radon
        summary["radon"] = parse_radon_cc_output(radon.stdout)
    else:
        summary["radon"] = {"blocks": 0, "average_complexity": None, "max_complexity": None,
                            "parse_error": False}

    for name, record in records.items():
        _write(out_dir / f"{name}.stdout.txt", record.stdout)
        _write(out_dir / f"{name}.stderr.txt", record.stderr)
    _write(
        out_dir / "commands.json",
        json.dumps({name: record.as_dict() for name, record in records.items()}, indent=2),
    )
    return summary


def run_native_gate(workspace: Path, out_dir: Path, *, run: RunSettings) -> dict[str, object]:
    """Arm-specific bonus signal: does the workspace's own quality gate pass?

    Only meaningful where a gate exists (the guardrails arm ships one); the
    result is reported per arm and never enters the cross-arm comparison.
    """
    gate = workspace / "scripts" / "quality_gate.py"
    if not gate.is_file():
        return {"present": False}
    record = _run(
        ("uv", "run", "python", "scripts/quality_gate.py"),
        cwd=workspace,
        timeout=run.gate_timeout_seconds,
    )
    _write(out_dir / "native_gate.stdout.txt", record.stdout)
    _write(out_dir / "native_gate.stderr.txt", record.stderr)
    return {
        "present": True,
        "passed": record.exit_code == 0,
        "exit_code": record.exit_code,
        "timed_out": record.timed_out,
        "duration_seconds": round(record.duration_seconds, 1),
    }
