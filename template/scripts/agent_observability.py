#!/usr/bin/env python3
"""Install, inspect, and query opt-in Langfuse tracing for coding agents."""

import argparse
from pathlib import Path
import sys

from scripts.agent_observability_controls import disable, status
from scripts.agent_observability_plugins import install
from scripts.agent_observability_support import OperatorError
from scripts.agent_observability_transcripts import analyze, export_session, recent


class Arguments(argparse.Namespace):
    def __init__(self) -> None:
        super().__init__()
        self.root: Path = Path()
        self.command: str = ""
        self.agent: str = "all"
        self.minutes: int = 60
        self.minimum_sessions: int = 2
        self.session_id: str = ""
        self.output: Path | None = None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install")
    _ = install_parser.add_argument("--agent", choices=("all", "codex", "claude"), default="all")
    _ = commands.add_parser("status")
    _ = commands.add_parser("disable")
    recent_parser = commands.add_parser("recent")
    _ = recent_parser.add_argument("--minutes", type=int, default=60)
    export_parser = commands.add_parser("export")
    _ = export_parser.add_argument("session_id")
    _ = export_parser.add_argument("--output", type=Path)
    analyze_parser = commands.add_parser("analyze")
    _ = analyze_parser.add_argument("--minutes", type=int, default=24 * 60)
    _ = analyze_parser.add_argument("--minimum-sessions", type=int, default=2)
    _ = analyze_parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args(namespace=Arguments())
    root = arguments.root.resolve()
    try:
        if arguments.command == "install":
            result = install(root, arguments.agent)
        elif arguments.command == "status":
            result = status(root)
        elif arguments.command == "disable":
            result = disable(root)
        elif arguments.command == "recent":
            result = recent(root, arguments.minutes)
        elif arguments.command == "analyze":
            result = analyze(
                root,
                arguments.minutes,
                arguments.minimum_sessions,
                arguments.output,
            )
        else:
            result = export_session(root, arguments.session_id, arguments.output)
    except OperatorError as error:
        print(f"agent observability: {error}", file=sys.stderr)
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
