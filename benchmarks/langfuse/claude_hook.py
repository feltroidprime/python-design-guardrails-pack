#!/usr/bin/env python3
"""Install, inspect, or remove the pinned Langfuse Claude Code plugin."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPOSITORY = "https://github.com/langfuse/Claude-Observability-Plugin.git"
REVISION = "3f301f3840c975bdbd16b8140140d139f27aa99b"
MARKETPLACE = "langfuse-observability"
PLUGIN = "langfuse-observability@langfuse-observability"


def _data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured) if configured else Path.home() / ".local" / "share"


PACKAGE_DATA = _data_home() / "python-design-guardrails-pack"
STATE_ROOT = PACKAGE_DATA / "langfuse-hook"
CHECKOUT = STATE_ROOT / f"plugin-{REVISION}"
STATE_FILE = STATE_ROOT / "state.json"


def _run(
    command: list[str], *, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=capture, check=check)


def _json_command(command: list[str]) -> list[dict[str, object]]:
    result = _run(command, capture=True)
    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        raise ValueError(f"unexpected output from {' '.join(command)}")
    return [item for item in payload if isinstance(item, dict)]


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if separator:
            values[name] = value
    return values


def _marketplace() -> dict[str, object] | None:
    entries = _json_command(["claude", "plugin", "marketplace", "list", "--json"])
    return next((item for item in entries if item.get("name") == MARKETPLACE), None)


def _plugin() -> dict[str, object] | None:
    entries = _json_command(["claude", "plugin", "list", "--json"])
    return next((item for item in entries if item.get("id") == PLUGIN), None)


def _marketplace_path(entry: dict[str, object]) -> Path | None:
    value = entry.get("path") or entry.get("installLocation")
    return Path(value).expanduser().resolve() if isinstance(value, str) else None


def install(env_file: Path) -> int:
    try:
        env = _read_env(env_file)
        public_key = env["LANGFUSE_PUBLIC_KEY"]
        secret_key = env["LANGFUSE_SECRET_KEY"]
        if not public_key or not secret_key:
            raise ValueError("Langfuse API keys are blank")

        marketplace = _marketplace()
        marketplace_path = _marketplace_path(marketplace) if marketplace else None
        if marketplace_path and not marketplace_path.is_relative_to(
            PACKAGE_DATA.resolve()
        ):
            print(
                f"refusing to replace unmanaged Claude marketplace at {marketplace_path}",
                file=sys.stderr,
            )
            return 2

        if _plugin() is not None:
            _run(
                [
                    "claude",
                    "plugin",
                    "uninstall",
                    "langfuse-observability",
                    "--scope",
                    "user",
                ]
            )
        if marketplace is not None:
            _run(
                [
                    "claude",
                    "plugin",
                    "marketplace",
                    "remove",
                    MARKETPLACE,
                    "--scope",
                    "user",
                ]
            )

        if STATE_ROOT.exists():
            shutil.rmtree(STATE_ROOT)
        STATE_ROOT.mkdir(parents=True, mode=0o700)
        _run(["git", "init", str(CHECKOUT)])
        _run(
            ["git", "-C", str(CHECKOUT), "fetch", "--depth", "1", REPOSITORY, REVISION]
        )
        _run(["git", "-C", str(CHECKOUT), "checkout", "--detach", "FETCH_HEAD"])
        actual = _run(
            ["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], capture=True
        ).stdout.strip()
        if actual != REVISION:
            raise RuntimeError(
                f"plugin checkout mismatch: expected {REVISION}, got {actual}"
            )

        _run(
            ["claude", "plugin", "marketplace", "add", str(CHECKOUT), "--scope", "user"]
        )
        _run(
            [
                "claude",
                "plugin",
                "install",
                PLUGIN,
                "--scope",
                "user",
                "--config",
                f"LANGFUSE_PUBLIC_KEY={public_key}",
                "--config",
                f"LANGFUSE_SECRET_KEY={secret_key}",
                "--config",
                "LANGFUSE_BASE_URL=http://127.0.0.1:3000",
            ]
        )
        STATE_FILE.write_text(
            json.dumps({"repository": REPOSITORY, "revision": REVISION}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    except (
        FileNotFoundError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
        RuntimeError,
    ) as error:
        print(f"hook installation failed: {error}", file=sys.stderr)
        return 1
    print(f"installed Langfuse Claude Code plugin at pinned revision {REVISION}")
    print("Restart Claude Code before testing a traced interactive session.")
    return 0


def uninstall() -> int:
    if not STATE_FILE.is_file():
        print("no repository-managed Langfuse Claude Code hook is installed")
        return 0
    try:
        marketplace = _marketplace()
        marketplace_path = _marketplace_path(marketplace) if marketplace else None
        if marketplace_path and not marketplace_path.is_relative_to(
            PACKAGE_DATA.resolve()
        ):
            print(
                f"refusing to remove unmanaged Claude marketplace at {marketplace_path}",
                file=sys.stderr,
            )
            return 2
        _run(
            [
                "claude",
                "plugin",
                "uninstall",
                "langfuse-observability",
                "--scope",
                "user",
            ],
            check=False,
        )
        if marketplace is not None:
            _run(
                [
                    "claude",
                    "plugin",
                    "marketplace",
                    "remove",
                    MARKETPLACE,
                    "--scope",
                    "user",
                ],
                check=False,
            )
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"hook removal failed: {error}", file=sys.stderr)
        return 1
    if STATE_ROOT.exists():
        shutil.rmtree(STATE_ROOT)
    print(
        "removed the Langfuse Claude Code plugin and its managed marketplace checkout"
    )
    return 0


def status() -> int:
    try:
        marketplace = _marketplace()
        plugin = _plugin()
        actual = _run(
            ["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], capture=True
        ).stdout.strip()
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
    ):
        print("Langfuse Claude Code hook is not installed by this repository.")
        return 1
    healthy = (
        marketplace is not None
        and plugin is not None
        and plugin.get("enabled") is True
        and actual == REVISION
    )
    if not healthy:
        print(
            "Langfuse Claude Code hook is missing, disabled, or not at the pinned revision."
        )
        return 1
    print(f"Langfuse Claude Code hook enabled at {REVISION}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--env-file", type=Path, default=HERE / ".env")
    subparsers.add_parser("uninstall")
    subparsers.add_parser("status")
    args = parser.parse_args()
    if args.command == "install":
        return install(args.env_file)
    if args.command == "uninstall":
        return uninstall()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
