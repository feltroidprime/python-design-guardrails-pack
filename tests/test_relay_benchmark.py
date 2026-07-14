"""Satisfiability proof for the shipped relay benchmark contract."""

from pathlib import Path
import shutil
import venv

from benchmarks.e2e.config import load_config
from benchmarks.e2e.probes import run_probes

REPO_ROOT = Path(__file__).resolve().parents[1]
RELAY_CONFIG = REPO_ROOT / "benchmarks" / "config" / "relay.toml"
REFERENCE_IMPLEMENTATION = REPO_ROOT / "tests" / "relay_reference.py"


def _reference_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "relay-reference-workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "relay-reference"\nversion = "0"\nrequires-python = ">=3.11"\n',
        encoding="utf-8",
    )
    venv.EnvBuilder(with_pip=False).create(workspace / ".venv")
    executable = workspace / ".venv" / "bin" / "relay"
    shutil.copyfile(REFERENCE_IMPLEMENTATION, executable)
    executable.chmod(0o755)
    return workspace


def test_full_relay_probe_scenario_is_satisfiable(tmp_path: Path) -> None:
    config = load_config(RELAY_CONFIG, repo_root=REPO_ROOT)
    results = run_probes(
        config.probes,
        _reference_workspace(tmp_path),
        tmp_path / "probe-state",
    )

    failures = [
        f"{result.name}: {result.failure}; stdout={result.stdout!r}; stderr={result.stderr!r}"
        for result in results
        if not result.passed
    ]
    assert not failures, "\n".join(failures)
