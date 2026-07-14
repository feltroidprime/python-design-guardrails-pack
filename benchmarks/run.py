#!/usr/bin/env python3
"""Entry point for the end-to-end value benchmark.

Standard-library launcher: it reads the config, then re-executes itself under
`uv run` with headless_llm installed (editable, from the path declared in the
config) plus the pinned Copier renderer, so the pack root keeps its
no-virtualenv, no-lock-file policy.

Usage:
    python3 benchmarks/run.py --config benchmarks/config/default.toml
"""

import argparse
import os
from pathlib import Path
import sys
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
_BOOTSTRAP_MARKER = "GUARDRAILS_BENCHMARK_BOOTSTRAPPED"


def _headless_path(config_path: Path) -> Path:
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    run_section = raw.get("run")
    declared = "../../headless_llm"
    if isinstance(run_section, dict) and isinstance(run_section.get("headless_llm_path"), str):
        declared = run_section["headless_llm_path"]
    path = Path(declared).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _bootstrap(config_path: Path) -> int:
    headless = _headless_path(config_path)
    if not (headless / "pyproject.toml").is_file():
        print(f"headless_llm checkout not found at {headless}", file=sys.stderr)
        print("set [run].headless_llm_path in the config file", file=sys.stderr)
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
        "rich==15.0.0",
        "--with",
        "copier==9.17.0",
        "python",
        "-u",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    environment = {**os.environ, _BOOTSTRAP_MARKER: "1"}
    os.execvpe(command[0], command, environment)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "benchmarks" / "config" / "default.toml",
        help="benchmark configuration file (TOML)",
    )
    parser.add_argument(
        "--builder-provider",
        choices=["claude", "codex", "opencode"],
        help="override the coding agent's provider from the config file",
    )
    parser.add_argument(
        "--builder-model",
        help="override the coding model (aliases: sonnet, opus, haiku; or any model id)",
    )
    parser.add_argument(
        "--builder-effort",
        help="override the coding agent's reasoning effort (e.g. medium, high)",
    )
    tui_group = parser.add_mutually_exclusive_group()
    tui_group.add_argument(
        "--tui",
        action="store_true",
        help="force the live dashboard even when auto-detection would skip it",
    )
    tui_group.add_argument(
        "--no-tui",
        action="store_true",
        help="plain line-by-line logs (default when stdout is not a terminal)",
    )
    arguments = parser.parse_args()
    config_path = arguments.config.expanduser().resolve()
    if not config_path.is_file():
        print(f"config file not found: {config_path}", file=sys.stderr)
        return 2

    # Always re-exec through uv when not yet bootstrapped: relying on an
    # ambient headless_llm import could silently benchmark a stale system
    # install while the manifest records the checkout's git revision.
    if _BOOTSTRAP_MARKER not in os.environ:
        return _bootstrap(config_path)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from benchmarks.e2e.agents import create_runner
    from benchmarks.e2e.config import ConfigError, apply_builder_overrides, load_config
    from benchmarks.e2e.orchestrator import run_benchmark

    try:
        cfg = load_config(config_path, repo_root=REPO_ROOT)
        cfg = apply_builder_overrides(
            cfg,
            provider=arguments.builder_provider,
            model=arguments.builder_model,
            effort=arguments.builder_effort,
        )
    except ConfigError as error:
        print(f"invalid configuration: {error}", file=sys.stderr)
        return 2
    print(f"app spec: {config_path.name} · builder: {cfg.builder.identity} "
          f"(effort {cfg.builder.effort or 'default'})")

    run = None
    if arguments.tui or (not arguments.no_tui and sys.stdout.isatty()):
        try:
            from benchmarks.e2e.tui import run_with_tui
        except ImportError as error:
            print(f"live dashboard unavailable ({error}); falling back to plain logs")
        else:
            run = run_with_tui(cfg, repo_root=REPO_ROOT, runner_factory=create_runner)
    if run is None:
        run = run_benchmark(cfg, repo_root=REPO_ROOT, runner_factory=create_runner)
    print(f"\nDone. Inspect: {run.run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
