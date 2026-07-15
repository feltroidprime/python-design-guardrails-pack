"""Behavioral tests for the generated agent-observability operator CLI."""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Thread


REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_REVISION = "3f301f3840c975bdbd16b8140140d139f27aa99b"
CLAUDE_PLUGIN = "langfuse-observability@langfuse-observability"
CODEX_REVISION = "33bc50ba75ef82ed1f3718df6fdd06cdbfc7c02e"


def _executable(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
    path.chmod(0o755)


def _fake_toolchain(tmp_path: Path) -> tuple[Path, Path]:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    command_log = tmp_path / "commands.log"
    logger = 'printf "%s %s\\n" "$0" "$*" >> "$COMMAND_LOG"\n'
    _executable(
        binaries / "codex",
        logger
        + """if [ "$1" = "--version" ]; then echo 'codex-cli 0.144.4'; exit 0; fi
exit 0
""",
    )
    _executable(
        binaries / "claude",
        logger
        + """plugin_state="${COMMAND_LOG}.claude-plugin"
marketplace_state="${COMMAND_LOG}.claude-marketplace"
if [ "$1" = "--version" ]; then echo '2.1.210 (Claude Code)'; exit 0; fi
if [ "$1 $2 $3" = "plugin list --json" ]; then
  if [ -f "$plugin_state" ]; then
    install_path=$(cat "$plugin_state")
    printf '[{"id":"langfuse-observability@langfuse-observability","scope":"local","enabled":true,"version":"1.0.0","installPath":"%s"}]\n' "$install_path"
  else
    echo '[]'
  fi
  exit 0
fi
if [ "$1 $2 $3" = "plugin marketplace list" ]; then
  if [ -f "$marketplace_state" ]; then
    marketplace_path=$(cat "$marketplace_state")
    printf '[{"name":"langfuse-observability","source":"directory","path":"%s"}]\n' "$marketplace_path"
  else
    echo '[]'
  fi
  exit 0
fi
if [ "$1 $2 $3" = "plugin marketplace add" ]; then
  printf '%s' "$4" > "$marketplace_state"
fi
if [ "$1 $2 $3" = "plugin marketplace remove" ]; then
  rm -f "$marketplace_state"
fi
if [ "$1 $2" = "plugin install" ]; then
  if [ "${FAIL_CLAUDE_INSTALL:-0}" = "1" ]; then
    echo 'simulated install failure' >&2
    exit 7
  fi
  install_path="${COMMAND_LOG}.claude-cache"
  rm -rf "$install_path"
  mkdir -p "$install_path/hooks"
  cp "$(cat "$marketplace_state")/hooks/langfuse_hook.py" "$install_path/hooks/langfuse_hook.py"
  printf '%s' "$install_path" > "$plugin_state"
fi
if [ "$1 $2" = "plugin uninstall" ]; then
  if [ "${FAIL_CLAUDE_UNINSTALL:-0}" = "1" ]; then
    echo 'simulated uninstall failure' >&2
    exit 8
  fi
  if [ -f "$plugin_state" ]; then rm -rf "$(cat "$plugin_state")"; fi
  rm -f "$plugin_state"
fi
exit 0
""",
    )
    _executable(
        binaries / "node",
        logger + 'if [ "$1" = "--version" ]; then echo \'v22.19.0\'; fi\n',
    )
    _executable(
        binaries / "git",
        logger
        + f"""if [ "$1" = "rev-parse" ]; then
  case "$PWD" in
    *wrong-marketplace*) echo '0000000000000000000000000000000000000000' ;;
    *codex-plugin-*) echo '{CODEX_REVISION}' ;;
    *) echo '{CLAUDE_REVISION}' ;;
  esac
fi
if [ "$1" = "status" ]; then
  case "$PWD" in
    *codex-plugin-*)
      if [ -s "$PWD/plugins/tracing/dist/index.mjs" ]; then
        echo ' M plugins/tracing/dist/index.mjs'
      fi
      ;;
  esac
  if [ -e "$PWD/hooks/shadow.py" ]; then echo '?? hooks/shadow.py'; fi
fi
if [ "$1" = "ls-files" ]; then
  case "$PWD" in
    *codex-plugin-*) printf 'plugins/tracing/dist/index.mjs\0' ;;
    *) printf 'hooks/langfuse_hook.py\0' ;;
  esac
fi
if [ "$1" = "init" ]; then
  mkdir -p "$2/.git"
  case "$2" in
    *codex-plugin-*)
      mkdir -p "$2/plugins/tracing/dist"
      : > "$2/plugins/tracing/dist/index.mjs"
      ;;
    *)
      mkdir -p "$2/hooks"
      printf 'reviewed hook\n' > "$2/hooks/langfuse_hook.py"
      ;;
  esac
fi
exit 0
""",
    )
    return binaries, command_log


def _run(
    root: Path,
    *arguments: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ if env is None else env)
    existing_pythonpath = environment.get("PYTHONPATH")
    template_path = str(REPO_ROOT / "template")
    environment["PYTHONPATH"] = (
        f"{template_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else template_path
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.agent_observability",
            "--root",
            str(root),
            *arguments,
        ],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_install_configures_both_pinned_plugins_without_printing_secrets(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    (root / ".copier-answers.yml").write_text(
        "_commit: v1.4.0\nproject_name: acme-orders\n", encoding="utf-8"
    )
    unrelated_hook = {
        "hooks": [{"command": "python3 scripts/unrelated_hook.py", "type": "command"}]
    }
    (root / ".codex").mkdir()
    (root / ".codex" / "hooks.json").write_text(
        json.dumps({"custom": "preserved", "hooks": {"Stop": [unrelated_hook]}}),
        encoding="utf-8",
    )
    checkout = root / ".agent-observability" / f"claude-plugin-{CLAUDE_REVISION}"
    (checkout / ".git").mkdir(parents=True)
    (checkout / "hooks").mkdir()
    (checkout / "hooks" / "langfuse_hook.py").write_text("reviewed hook\n", encoding="utf-8")
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-super-secret",
        "LANGFUSE_BASE_URL": "https://langfuse.example.test",
    }

    result = _run(root, "install", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "sk-lf-super-secret" not in result.stdout + result.stderr
    commands = command_log.read_text(encoding="utf-8")
    assert "sk-lf-super-secret" not in commands
    assert "codex plugin" not in commands
    assert (
        "fetch --depth 1 https://github.com/langfuse/codex-observability-plugin.git "
        f"{CODEX_REVISION}" in commands
    )
    assert "rev-parse HEAD" in commands
    assert "plugin marketplace add" in commands
    assert "plugin install langfuse-observability@langfuse-observability --scope local" in commands

    codex = json.loads((root / ".codex" / "langfuse.json").read_text(encoding="utf-8"))
    assert codex == {
        "base_url": "https://langfuse.example.test",
        "enabled": True,
        "max_chars": 2_147_483_647,
        "metadata": {
            "repository": "acme-orders",
            "repository_root": str(root),
            "template_version": "v1.4.0",
        },
        "public_key": "pk-lf-test",
        "secret_key": "sk-lf-super-secret",
        "tags": ["python-design-guardrails-pack", "repository:acme-orders"],
    }
    claude = json.loads((root / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert claude["env"] == {
        "CC_LANGFUSE_MAX_CHARS": "2147483647",
        "CC_LANGFUSE_CAPTURE_SKILL_CONTENT": "true",
        "LANGFUSE_BASE_URL": "https://langfuse.example.test",
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-super-secret",
    }
    assert (root / ".codex" / "langfuse.json").stat().st_mode & 0o777 == 0o600
    hooks_path = root / ".codex" / "hooks.json"
    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    assert hooks["custom"] == "preserved"
    assert hooks["hooks"]["Stop"][0] == unrelated_hook
    managed_hook = hooks["hooks"]["Stop"][1]["hooks"][0]
    hook_command = managed_hook["command"]
    assert "agent_observability_codex_hook.py" in hook_command
    assert f"codex-plugin-{CODEX_REVISION}/plugins/tracing/dist/index.mjs" in hook_command
    assert managed_hook["command_windows"].startswith("py -3 ")
    assert hooks_path.stat().st_mode & 0o777 == 0o600
    assert (root / ".claude" / "settings.local.json").stat().st_mode & 0o777 == 0o600

    status = _run(root, "status", env=env)
    assert status.returncode == 0, status.stdout + status.stderr
    assert "Codex: ready" in status.stdout
    assert "Claude Code: ready" in status.stdout


def test_invalid_capture_limit_fails_before_plugin_mutation(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
        "AGENT_OBSERVABILITY_MAX_CHARS": "unbounded",
    }

    result = _run(root, "install", env=env)

    assert result.returncode == 1
    assert "must be a positive integer" in result.stderr
    assert not command_log.exists()
    assert not (root / ".codex").exists()
    assert not (root / ".claude").exists()


def test_codex_hook_runs_pinned_entrypoint_from_repository_root(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    runner = root / "scripts" / "agent_observability_codex_hook.py"
    runner.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "template" / "scripts" / runner.name, runner)
    entrypoint = (
        root
        / ".agent-observability"
        / f"codex-plugin-{CODEX_REVISION}"
        / "plugins"
        / "tracing"
        / "dist"
        / "index.mjs"
    )
    entrypoint.parent.mkdir(parents=True)
    entrypoint.touch()
    config = root / ".codex" / "langfuse.json"
    config.parent.mkdir()
    config.write_text('{"enabled":true}\n', encoding="utf-8")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    hook_log = tmp_path / "hook.log"
    _executable(
        binaries / "node",
        'printf "%s\\n%s\\n" "$PWD" "$1" > "$HOOK_LOG"\ncat >> "$HOOK_LOG"\n',
    )
    _executable(
        binaries / "git",
        f"""if [ "$1" = "rev-parse" ]; then echo '{CODEX_REVISION}'; fi
exit 0
""",
    )
    nested = root / "src" / "feature"
    nested.mkdir(parents=True)

    result = subprocess.run(
        [sys.executable, str(runner), str(entrypoint), CODEX_REVISION],
        cwd=nested,
        env={
            **os.environ,
            "HOOK_LOG": str(hook_log),
            "PATH": f"{binaries}:{os.environ['PATH']}",
        },
        input='{"session_id":"session-abc"}',
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert hook_log.read_text(encoding="utf-8").splitlines() == [
        str(root),
        str(entrypoint),
        '{"session_id":"session-abc"}',
    ]


def test_default_install_requires_both_agents_before_mutation(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    (binaries / "claude").unlink()
    env = {
        **os.environ,
        "PATH": str(binaries),
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }

    result = _run(root, "install", env=env)

    assert result.returncode == 1
    assert "required command missing: claude" in result.stderr
    assert not command_log.exists()
    assert not (root / ".agent-observability").exists()
    assert not (root / ".codex").exists()


def test_status_only_requires_the_agent_selected_for_this_project(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }

    install_result = _run(root, "install", "--agent", "codex", env=env)
    status_result = _run(root, "status", env=env)

    assert install_result.returncode == 0, install_result.stdout + install_result.stderr
    assert status_result.returncode == 0, status_result.stdout + status_result.stderr
    assert "Codex: ready" in status_result.stdout
    assert "Claude Code: not managed by this project" in status_result.stdout
    assert not (root / ".claude").exists()


def test_codex_status_rejects_and_reinstall_repairs_a_dirty_checkout(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }
    installed = _run(root, "install", "--agent", "codex", env=env)
    entrypoint = (
        root
        / ".agent-observability"
        / f"codex-plugin-{CODEX_REVISION}"
        / "plugins"
        / "tracing"
        / "dist"
        / "index.mjs"
    )
    entrypoint.write_text("tampered", encoding="utf-8")

    dirty_status = _run(root, "status", env=env)
    repaired = _run(root, "install", "--agent", "codex", env=env)

    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert dirty_status.returncode == 1
    assert "Codex: not configured" in dirty_status.stdout
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    assert entrypoint.read_text(encoding="utf-8") == ""


def test_sequential_agent_install_preserves_existing_managed_state(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }

    codex = _run(root, "install", "--agent", "codex", env=env)
    claude = _run(root, "install", "--agent", "claude", env=env)

    assert codex.returncode == 0, codex.stdout + codex.stderr
    assert claude.returncode == 0, claude.stdout + claude.stderr
    state = json.loads((root / ".agent-observability" / "install.json").read_text(encoding="utf-8"))
    assert state["agents"] == ["codex", "claude"]
    status_result = _run(root, "status", env=env)
    assert status_result.returncode == 0, status_result.stdout + status_result.stderr
    assert "Codex: ready" in status_result.stdout
    assert "Claude Code: ready" in status_result.stdout

    rotated = _run(
        root,
        "install",
        "--agent",
        "codex",
        env={**env, "LANGFUSE_SECRET_KEY": "sk-lf-rotated"},
    )

    assert rotated.returncode == 0, rotated.stdout + rotated.stderr
    codex_config = json.loads((root / ".codex" / "langfuse.json").read_text(encoding="utf-8"))
    claude_settings = json.loads(
        (root / ".claude" / "settings.local.json").read_text(encoding="utf-8")
    )
    assert codex_config["secret_key"] == "sk-lf-rotated"
    assert claude_settings["env"]["LANGFUSE_SECRET_KEY"] == "sk-lf-rotated"


def test_sequential_install_rejects_a_different_langfuse_project(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-project-a",
        "LANGFUSE_SECRET_KEY": "sk-lf-project-a",
        "LANGFUSE_BASE_URL": "https://langfuse-a.example.test",
    }
    first = _run(root, "install", "--agent", "codex", env=env)
    commands_before = command_log.read_text(encoding="utf-8")

    second = _run(
        root,
        "install",
        "--agent",
        "claude",
        env={
            **env,
            "LANGFUSE_PUBLIC_KEY": "pk-lf-project-b",
            "LANGFUSE_SECRET_KEY": "sk-lf-project-b",
            "LANGFUSE_BASE_URL": "https://langfuse-b.example.test",
        },
    )

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 1
    assert "must match the existing project installation" in second.stderr
    assert command_log.read_text(encoding="utf-8") == commands_before
    state = json.loads((root / ".agent-observability" / "install.json").read_text(encoding="utf-8"))
    assert state["agents"] == ["codex"]


def test_claude_install_refuses_unmanaged_local_langfuse_state(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    (Path(f"{command_log}.claude-plugin")).touch()
    settings = root / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    original = {
        "enabledPlugins": {CLAUDE_PLUGIN: True},
        "env": {"LANGFUSE_SECRET_KEY": "unmanaged-secret"},
        "permissions": {"allow": ["Read"]},
    }
    settings.write_text(json.dumps(original), encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }

    result = _run(root, "install", "--agent", "claude", env=env)

    assert result.returncode == 1
    assert "already exists outside project management" in result.stderr
    assert json.loads(settings.read_text(encoding="utf-8")) == original
    assert not (root / ".agent-observability" / "install.json").exists()
    commands = command_log.read_text(encoding="utf-8")
    assert "plugin list --json" in commands
    assert "plugin uninstall" not in commands
    assert "plugin marketplace" not in commands


def test_claude_reuses_but_does_not_own_an_exact_global_marketplace(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    global_marketplace = tmp_path / "global-marketplace"
    (global_marketplace / ".git").mkdir(parents=True)
    (global_marketplace / "hooks").mkdir()
    (global_marketplace / "hooks" / "langfuse_hook.py").write_text(
        "reviewed hook\n", encoding="utf-8"
    )
    marketplace_state = Path(f"{command_log}.claude-marketplace")
    marketplace_state.write_text(str(global_marketplace), encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }

    installed = _run(root, "install", "--agent", "claude", env=env)
    status_result = _run(root, "status", env=env)
    state = json.loads((root / ".agent-observability" / "install.json").read_text(encoding="utf-8"))
    shadow = global_marketplace / "hooks" / "shadow.py"
    shadow.write_text("untracked shadow\n", encoding="utf-8")
    source_dirty_status = _run(root, "status", env=env)
    shadow.unlink()
    cache_path = Path(Path(f"{command_log}.claude-plugin").read_text(encoding="utf-8"))
    unexpected_cache_file = cache_path / "hooks" / "unexpected.py"
    unexpected_cache_file.write_text("unexpected cache file\n", encoding="utf-8")
    unexpected_cache_status = _run(root, "status", env=env)
    unexpected_cache_file.unlink()
    (cache_path / "hooks" / "langfuse_hook.py").write_text("tampered cache\n", encoding="utf-8")
    tampered_status = _run(root, "status", env=env)
    disabled = _run(root, "disable", env=env)

    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert status_result.returncode == 0, status_result.stdout + status_result.stderr
    assert "Claude Code: ready" in status_result.stdout
    assert source_dirty_status.returncode == 1
    assert "Claude Code: not configured" in source_dirty_status.stdout
    assert unexpected_cache_status.returncode == 1
    assert "Claude Code: not configured" in unexpected_cache_status.stdout
    assert tampered_status.returncode == 1
    assert "Claude Code: not configured" in tampered_status.stdout
    assert disabled.returncode == 0, disabled.stdout + disabled.stderr
    assert state["claude_marketplace_owned"] is False
    assert marketplace_state.read_text(encoding="utf-8") == str(global_marketplace)
    commands = command_log.read_text(encoding="utf-8")
    assert "plugin marketplace add" not in commands
    assert "plugin marketplace remove" not in commands


def test_claude_rejects_a_global_marketplace_at_another_revision(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    wrong_marketplace = tmp_path / "wrong-marketplace"
    (wrong_marketplace / ".git").mkdir(parents=True)
    marketplace_state = Path(f"{command_log}.claude-marketplace")
    marketplace_state.write_text(str(wrong_marketplace), encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }

    result = _run(root, "install", "--agent", "claude", env=env)

    assert result.returncode == 1
    assert "not at the reviewed revision" in result.stderr
    assert not (root / ".agent-observability" / "install.json").exists()
    assert marketplace_state.read_text(encoding="utf-8") == str(wrong_marketplace)


def test_failed_claude_install_leaves_reversible_owned_state(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
        "FAIL_CLAUDE_INSTALL": "1",
    }

    install_result = _run(root, "install", "--agent", "claude", env=env)
    disable_result = _run(root, "disable", env=env)

    assert install_result.returncode == 1
    assert "simulated install failure" in install_result.stderr
    assert disable_result.returncode == 0, disable_result.stdout + disable_result.stderr
    assert not (root / ".agent-observability" / "install.json").exists()
    assert not (root / ".agent-observability" / f"claude-plugin-{CLAUDE_REVISION}").exists()
    assert not (root / ".claude" / "settings.local.json").exists()


def test_disable_scrubs_project_credentials_and_keeps_explicit_opt_out(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    (root / ".codex").mkdir()
    (root / ".codex" / "langfuse.json").write_text(
        '{"enabled":true,"secret_key":"secret"}\n', encoding="utf-8"
    )
    unrelated_hooks = {
        "custom": "preserved",
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "command": "python3 scripts/unrelated_hook.py",
                            "type": "command",
                        }
                    ]
                },
                {
                    "hooks": [
                        {
                            "command": "python3 scripts/agent_observability_codex_hook.py hook.mjs",
                            "statusMessage": "Uploading Codex trace to Langfuse",
                            "type": "command",
                        }
                    ]
                },
            ]
        },
    }
    (root / ".codex" / "hooks.json").write_text(json.dumps(unrelated_hooks), encoding="utf-8")
    codex_checkout = root / ".agent-observability" / f"codex-plugin-{CODEX_REVISION}"
    (codex_checkout / ".git").mkdir(parents=True)
    state = root / ".agent-observability" / "install.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "agents": ["codex", "claude"],
                "codex_revision": CODEX_REVISION,
                "claude_revision": CLAUDE_REVISION,
                "max_capture_chars": 2_147_483_647,
            }
        ),
        encoding="utf-8",
    )
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.local.json").write_text(
        json.dumps(
            {
                "enabledPlugins": {
                    "langfuse-observability@langfuse-observability": True,
                    "someone-else@example": True,
                },
                "env": {
                    "LANGFUSE_SECRET_KEY": "secret",
                    "UNRELATED": "preserved",
                },
            }
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
    }
    Path(f"{command_log}.claude-plugin").write_text(
        str(tmp_path / "claude-cache"), encoding="utf-8"
    )

    result = _run(root, "disable", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((root / ".codex" / "langfuse.json").read_text()) == {"enabled": False}
    remaining_hooks = json.loads((root / ".codex" / "hooks.json").read_text())
    assert remaining_hooks["custom"] == "preserved"
    assert remaining_hooks["hooks"]["Stop"] == [unrelated_hooks["hooks"]["Stop"][0]]
    assert not codex_checkout.exists()
    claude = json.loads((root / ".claude" / "settings.local.json").read_text())
    assert claude == {
        "enabledPlugins": {
            "someone-else@example": True,
        },
        "env": {"UNRELATED": "preserved"},
    }
    assert "plugin uninstall langfuse-observability --scope local" in command_log.read_text()


def test_disable_scrubs_secrets_but_preserves_owned_state_without_claude(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    install_env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }
    installed = _run(root, "install", "--agent", "claude", env=install_env)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    state = root / ".agent-observability" / "install.json"
    checkout = root / ".agent-observability" / f"claude-plugin-{CLAUDE_REVISION}"
    (binaries / "claude").rename(binaries / "claude.unavailable")

    disabled = _run(
        root,
        "disable",
        env={**install_env, "PATH": str(binaries)},
    )

    assert disabled.returncode == 1
    assert "required command is not installed: claude" in disabled.stderr
    assert state.exists()
    assert checkout.exists()
    assert not (root / ".claude" / "settings.local.json").exists()


def test_disable_can_retry_after_claude_uninstall_failure(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    binaries, command_log = _fake_toolchain(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "COMMAND_LOG": str(command_log),
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
    }
    installed = _run(root, "install", "--agent", "claude", env=env)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    state = root / ".agent-observability" / "install.json"

    failed = _run(root, "disable", env={**env, "FAIL_CLAUDE_UNINSTALL": "1"})

    assert failed.returncode == 1
    assert "simulated uninstall failure" in failed.stderr
    assert state.exists()
    assert not (root / ".claude" / "settings.local.json").exists()

    retried = _run(root, "disable", env=env)

    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert not state.exists()
    assert not (root / ".claude" / "settings.local.json").exists()


def test_recent_and_export_make_a_complete_session_available_locally(
    tmp_path: Path,
) -> None:
    requests: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            requests.append((self.path, self.headers.get("Authorization")))
            if self.path.startswith("/api/public/traces/trace-123"):
                payload = {
                    "id": "trace-123",
                    "name": "Codex Turn",
                    "sessionId": "session-abc",
                    "timestamp": "2026-07-15T12:00:00.000Z",
                    "metadata": {"repository_root": str(root)},
                    "observations": [
                        {
                            "name": "Tool: Bash",
                            "input": {"command": "just check"},
                            "output": "E501 Line too long (109 > 100)",
                        }
                    ],
                }
            else:
                payload = {
                    "data": [
                        {
                            "id": "trace-123",
                            "name": "Codex Turn",
                            "sessionId": "session-abc",
                            "timestamp": "2026-07-15T12:00:00.000Z",
                            "metadata": {"repository_root": str(root)},
                        }
                    ],
                    "meta": {"page": 1, "totalPages": 1},
                }
            body = json.dumps(payload).encode("utf-8")
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
    root = tmp_path / "generated"
    config = root / ".codex" / "langfuse.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "enabled": True,
                "public_key": "pk-lf-test",
                "secret_key": "sk-lf-test",
                "base_url": f"http://127.0.0.1:{server.server_port}",
            }
        ),
        encoding="utf-8",
    )
    try:
        recent = _run(root, "recent", "--minutes", "30")
        exported = _run(root, "export", "session-abc")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert recent.returncode == 0, recent.stdout + recent.stderr
    assert "session-abc" in recent.stdout
    assert "trace-123" in recent.stdout
    assert exported.returncode == 0, exported.stdout + exported.stderr
    output = root / ".agent-observability" / "transcripts" / "session-abc.json"
    transcript = json.loads(output.read_text(encoding="utf-8"))
    assert transcript["session_id"] == "session-abc"
    assert transcript["traces"][0]["observations"][0]["output"] == (
        "E501 Line too long (109 > 100)"
    )
    assert output.stat().st_mode & 0o777 == 0o600
    assert any("sessionId=session-abc" in path for path, _ in requests)
    expected_auth = "Basic " + base64.b64encode(b"pk-lf-test:sk-lf-test").decode()
    assert all(authorization == expected_auth for _, authorization in requests)


def test_recent_pages_past_unrelated_traces_in_a_shared_project(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/api/public/traces/trace-"):
                trace_id = self.path.rsplit("/", maxsplit=1)[-1]
                matching = trace_id == "trace-matching"
                payload = {
                    "id": trace_id,
                    "name": "Claude Turn",
                    "sessionId": "session-matching" if matching else "session-unrelated",
                    "timestamp": "2026-07-15T12:00:00.000Z",
                    "metadata": {
                        "cwd": str(
                            (tmp_path / "generated" / "src")
                            if matching
                            else (tmp_path / "unrelated")
                        )
                    },
                }
            else:
                second_page = "page=2" in self.path
                payload = {
                    "data": [
                        {
                            "id": "trace-matching" if second_page else "trace-unrelated",
                        }
                    ],
                    "meta": {"page": 2 if second_page else 1, "totalPages": 2},
                }
            body = json.dumps(payload).encode("utf-8")
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
    root = tmp_path / "generated"
    config = root / ".codex" / "langfuse.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "enabled": True,
                "public_key": "pk-lf-test",
                "secret_key": "sk-lf-test",
                "base_url": f"http://127.0.0.1:{server.server_port}",
            }
        ),
        encoding="utf-8",
    )
    try:
        recent = _run(root, "recent", "--minutes", "30")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert recent.returncode == 0, recent.stdout + recent.stderr
    assert "session-matching" in recent.stdout
    assert "session-unrelated" not in recent.stdout


def test_analyze_exports_a_multi_session_corpus_and_recurring_diagnostics(
    tmp_path: Path,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/api/public/traces/trace-"):
                trace_id = self.path.rsplit("/", maxsplit=1)[-1]
                output = "src/app.py:8: E501 Line too long (109 > 100)"
                if trace_id == "trace-1":
                    output = f"{output}\n{output}"
                metadata = {"repository_root": str(tmp_path / "generated")}
                if trace_id == "trace-2":
                    metadata = {"cwd": str(tmp_path / "generated" / "src")}
                elif trace_id == "trace-3":
                    metadata = {"cwd": str(tmp_path / "unrelated")}
                payload = {
                    "id": trace_id,
                    "sessionId": f"session-{trace_id[-1]}",
                    "metadata": metadata,
                    "observations": [
                        {
                            "name": "Tool: Bash",
                            "output": output,
                        }
                    ],
                }
            else:
                payload = {
                    "data": [
                        {
                            "id": "trace-1",
                            "sessionId": "session-1",
                            "timestamp": "2026-07-15T12:00:00.000Z",
                        },
                        {
                            "id": "trace-2",
                            "sessionId": "session-2",
                            "timestamp": "2026-07-15T12:10:00.000Z",
                        },
                        {
                            "id": "trace-3",
                            "sessionId": "session-3",
                            "timestamp": "2026-07-15T12:20:00.000Z",
                        },
                    ],
                    "meta": {"page": 1, "totalPages": 1},
                }
            body = json.dumps(payload).encode("utf-8")
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
    root = tmp_path / "generated"
    config = root / ".codex" / "langfuse.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "enabled": True,
                "public_key": "pk-lf-test",
                "secret_key": "sk-lf-test",
                "base_url": f"http://127.0.0.1:{server.server_port}",
            }
        ),
        encoding="utf-8",
    )
    try:
        analyzed = _run(root, "analyze", "--minutes", "180")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert analyzed.returncode == 0, analyzed.stdout + analyzed.stderr
    assert "E501" in analyzed.stdout
    output = root / ".agent-observability" / "analysis" / "latest.json"
    corpus = json.loads(output.read_text(encoding="utf-8"))
    assert corpus["trace_count"] == 2
    assert corpus["session_count"] == 2
    assert corpus["diagnostics"] == [
        {
            "code": "E501",
            "occurrences": 3,
            "samples": ["Line too long (109 > 100)"],
            "session_count": 2,
            "trace_count": 2,
        }
    ]
    assert len(corpus["traces"]) == 2
    assert output.stat().st_mode & 0o777 == 0o600
