#!/usr/bin/env python3
"""Launch a benchmark matrix campaign, or print its exact dry-run plan."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
_BOOTSTRAP_MARKER = "GUARDRAILS_MATRIX_BOOTSTRAPPED"


def _headless_path(config_path: Path) -> Path:
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    run = raw.get("run")
    declared = "../../headless_llm"
    if isinstance(run, dict) and isinstance(run.get("headless_llm_path"), str):
        declared = run["headless_llm_path"]
    path = Path(declared).expanduser()
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _bootstrap(config_path: Path) -> int:
    headless = _headless_path(config_path)
    if not (headless / "pyproject.toml").is_file():
        print(
            f"headless_llm provider checkout not found at {headless}", file=sys.stderr
        )
        print("set [run].headless_llm_path in the matrix config", file=sys.stderr)
        return 2
    command = [
        "uv",
        "run",
        "--no-project",
        "--python",
        "3.14",
        "--with-editable",
        str(headless),
        "--with",
        "copier==9.17.0",
        "python",
        "-u",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    os.execvpe(command[0], command, {**os.environ, _BOOTSTRAP_MARKER: "1"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="matrix TOML file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print every planned cell and exit without creating output or calling providers",
    )
    arguments = parser.parse_args(argv)
    config_path = arguments.config.expanduser().resolve()
    if not config_path.is_file():
        print(f"matrix config file not found: {config_path}", file=sys.stderr)
        return 2

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from benchmarks.e2e.config import ConfigError
    from benchmarks.e2e.matrix import load_matrix_config, run_matrix

    try:
        matrix = load_matrix_config(config_path, repo_root=REPO_ROOT)
    except ConfigError as error:
        print(f"invalid matrix configuration: {error}", file=sys.stderr)
        return 2

    if arguments.dry_run:
        run_matrix(
            matrix,
            repo_root=REPO_ROOT,
            runner_factory=lambda role: (_ for _ in ()).throw(
                AssertionError(f"dry-run created runner for {role.identity}")
            ),
            dry_run=True,
        )
        return 0

    if _BOOTSTRAP_MARKER not in os.environ:
        return _bootstrap(config_path)

    from benchmarks.e2e.agents import create_runner

    result = run_matrix(matrix, repo_root=REPO_ROOT, runner_factory=create_runner)
    print(
        f"\nDone. Completed {len(result.completed)} cells; "
        f"skipped {len(result.skipped)} completed cells."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
