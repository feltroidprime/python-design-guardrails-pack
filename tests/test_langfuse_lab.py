"""Deterministic contract tests for the optional local Langfuse lab."""

from pathlib import Path
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


REPO_ROOT = Path(__file__).resolve().parents[1]
LANGFUSE_DIR = REPO_ROOT / "benchmarks" / "langfuse"
COMPOSE_FILE = LANGFUSE_DIR / "compose.yaml"


def test_compose_images_are_exactly_pinned() -> None:
    image_lines = re.findall(
        r"^\s*image:\s*([^\s#]+)",
        COMPOSE_FILE.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )

    assert set(image_lines) == {
        "docker.io/langfuse/langfuse:3.212.0",
        "docker.io/langfuse/langfuse-worker:3.212.0",
        "docker.io/postgres:17.10-alpine3.24",
        "docker.io/redis:7.4.9-alpine3.21",
        "docker.io/clickhouse/clickhouse-server:25.8.28.1-alpine",
        "docker.io/minio/minio:RELEASE.2025-09-07T16-13-09Z",
    }
    assert len(image_lines) == 6
    assert all(not image.endswith(":latest") for image in image_lines)


def test_real_env_is_ignored_and_example_documents_compose_variables() -> None:
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    compose_variables = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)\}", compose_text))
    example_text = (LANGFUSE_DIR / ".env.example").read_text(encoding="utf-8")
    example_variables = set(
        re.findall(r"^([A-Z][A-Z0-9_]*)=", example_text, re.MULTILINE)
    )

    assert example_variables == compose_variables
    for secret_name in (
        "POSTGRES_PASSWORD",
        "CLICKHOUSE_PASSWORD",
        "REDIS_AUTH",
        "MINIO_ROOT_PASSWORD",
        "SALT",
        "ENCRYPTION_KEY",
        "NEXTAUTH_SECRET",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_INIT_USER_PASSWORD",
    ):
        assert re.search(rf"^{secret_name}=$", example_text, re.MULTILINE)

    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "benchmarks/langfuse/.env"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert ignored.returncode == 0


def test_init_cli_writes_private_complete_env_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / ".env"
    command = [
        sys.executable,
        str(LANGFUSE_DIR / "init_env.py"),
        "--output",
        str(output),
    ]

    first = subprocess.run(
        command, cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    assert first.returncode == 0, first.stderr
    values = dict(
        line.split("=", 1)
        for line in output.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert values.keys() >= {
        "POSTGRES_PASSWORD",
        "ENCRYPTION_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    }
    assert all(values.values())
    assert len(values["ENCRYPTION_KEY"]) == 64
    assert values["LANGFUSE_PUBLIC_KEY"].startswith("pk-lf-")
    assert values["LANGFUSE_SECRET_KEY"].startswith("sk-lf-")
    assert output.stat().st_mode & 0o777 == 0o600

    second = subprocess.run(
        command, cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    assert second.returncode != 0
    assert "already exists" in second.stderr


def test_just_exposes_langfuse_operator_commands() -> None:
    result = subprocess.run(
        ["just", "--list", "--unsorted"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    for recipe in (
        "langfuse-init",
        "langfuse-up",
        "langfuse-status",
        "langfuse-down",
        "langfuse-traces",
        "langfuse-hook-install",
        "langfuse-hook-status",
        "langfuse-hook-uninstall",
    ):
        assert recipe in result.stdout


def test_recent_traces_cli_queries_public_api_with_env_credentials(
    tmp_path: Path,
) -> None:
    requests: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            requests.append((self.path, self.headers.get("Authorization")))
            body = (
                b'{"data":[{"id":"trace-123","name":"claude-code",'
                b'"timestamp":"2026-07-14T10:00:00.000Z"}],"meta":{"totalItems":1}}'
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LANGFUSE_PUBLIC_KEY=pk-lf-test\nLANGFUSE_SECRET_KEY=sk-lf-test\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(LANGFUSE_DIR / "recent_traces.py"),
                "--env-file",
                str(env_file),
                "--base-url",
                f"http://127.0.0.1:{server.server_port}",
                "--minutes",
                "15",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert result.returncode == 0, result.stderr
    assert "trace-123" in result.stdout
    assert "claude-code" in result.stdout
    assert len(requests) == 1
    path, authorization = requests[0]
    assert path.startswith("/api/public/traces?")
    assert "limit=20" in path
    assert "fromTimestamp=" in path
    assert authorization == "Basic cGstbGYtdGVzdDpzay1sZi10ZXN0"


def test_hook_cli_installs_pinned_plugin_and_uninstalls_reversibly(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "commands.log"
    git = fake_bin / "git"
    git.write_text(
        """#!/bin/sh
printf 'git %s\\n' "$*" >> "$COMMAND_LOG"
if [ "$1" = "init" ]; then mkdir -p "$2/.git"; fi
if [ "$1" = "-C" ] && [ "$3" = "rev-parse" ]; then
  echo 3f301f3840c975bdbd16b8140140d139f27aa99b
fi
""",
        encoding="utf-8",
    )
    claude = fake_bin / "claude"
    claude.write_text(
        """#!/bin/sh
printf 'claude %s\\n' "$*" >> "$COMMAND_LOG"
if [ "$1 $2 $3" = "plugin marketplace list" ]; then
  printf '[{"name":"langfuse-observability","path":"%s/python-design-guardrails-pack/langfuse-hook/plugin-3f301f3840c975bdbd16b8140140d139f27aa99b"}]\n' "$XDG_DATA_HOME"
fi
if [ "$1 $2" = "plugin list" ]; then echo '[]'; fi
""",
        encoding="utf-8",
    )
    git.chmod(0o755)
    claude.chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LANGFUSE_PUBLIC_KEY=pk-lf-test\nLANGFUSE_SECRET_KEY=sk-lf-test\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "COMMAND_LOG": str(log),
    }
    command = [sys.executable, str(LANGFUSE_DIR / "claude_hook.py")]

    installed = subprocess.run(
        [*command, "install", "--env-file", str(env_file)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    assert "sk-lf-test" not in installed.stdout + installed.stderr
    commands = log.read_text(encoding="utf-8")
    assert (
        "fetch --depth 1 https://github.com/langfuse/Claude-Observability-Plugin.git 3f301f3840c975bdbd16b8140140d139f27aa99b"
        in commands
    )
    assert "plugin marketplace add" in commands
    assert (
        "plugin install langfuse-observability@langfuse-observability --scope user"
        in commands
    )

    uninstalled = subprocess.run(
        [*command, "uninstall"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert uninstalled.returncode == 0, uninstalled.stderr
    commands = log.read_text(encoding="utf-8")
    assert "plugin uninstall langfuse-observability --scope user" in commands
    assert "plugin marketplace remove langfuse-observability --scope user" in commands
    state_root = tmp_path / "data" / "python-design-guardrails-pack" / "langfuse-hook"
    assert not state_root.exists()


def test_benchmark_docs_register_operations_and_neutrality_limit() -> None:
    benchmark_readme = (REPO_ROOT / "benchmarks" / "README.md").read_text(
        encoding="utf-8"
    )
    lab_readme = (LANGFUSE_DIR / "README.md").read_text(encoding="utf-8")

    assert "[Local Langfuse operations](langfuse/README.md)" in benchmark_readme
    assert "Langfuse Claude Code hook" in benchmark_readme
    assert "symmetric between arms" in benchmark_readme
    for phrase in (
        "just langfuse-init",
        "just langfuse-up",
        "just langfuse-status",
        "just langfuse-down",
        "just langfuse-hook-install",
        "just langfuse-hook-uninstall",
        "just langfuse-traces",
        "3f301f3840c975bdbd16b8140140d139f27aa99b",
        "/api/public/otel/v1/traces",
        "Troubleshooting",
    ):
        assert phrase in lab_readme, phrase
