"""Readiness checks and reversible project-level tracing disablement."""

import shutil
from typing import TYPE_CHECKING, cast

from scripts.agent_observability_claude import (
    CLAUDE_MARKETPLACE,
    CLAUDE_PLUGIN,
    CLAUDE_REVISION,
    LANGFUSE_ENV_KEYS,
    claude_marketplace_status,
    claude_plugin_status,
)
from scripts.agent_observability_codex_hook import (
    codex_hook_group,
    codex_hook_is_configured,
    remove_codex_hook,
)
from scripts.agent_observability_plugins import CODEX_REVISION
from scripts.agent_observability_support import (
    OperatorError,
    object_mapping,
    read_json,
    run_command,
    write_private_json,
)

if TYPE_CHECKING:
    from pathlib import Path


def _claude_plugin_is_enabled(root: Path) -> bool:
    checkout = root / ".agent-observability" / f"claude-plugin-{CLAUDE_REVISION}"
    _, enabled = claude_plugin_status(root, checkout)
    return enabled


def _revision_matches(checkout: Path, expected: str) -> bool:
    if not (checkout / ".git").exists():
        return False
    result = run_command(("git", "rev-parse", "HEAD"), cwd=checkout, check=False)
    cleanliness = run_command(
        ("git", "status", "--porcelain"),
        cwd=checkout,
        check=False,
    )
    return (
        result.returncode == 0
        and result.stdout.strip() == expected
        and cleanliness.returncode == 0
        and not cleanliness.stdout.strip()
    )


def _has_text(mapping: dict[str, object], name: str) -> bool:
    return isinstance(mapping.get(name), str) and bool(mapping[name])


def _managed_agents(state: dict[str, object]) -> set[str]:
    agents_value = state.get("agents")
    if not isinstance(agents_value, list):
        return set()
    return {agent for agent in cast("list[object]", agents_value) if isinstance(agent, str)}


def _managed_secrets_match(root: Path, managed: set[str]) -> bool:
    if not {"codex", "claude"}.issubset(managed):
        return True
    codex = read_json(root / ".codex" / "langfuse.json").get("secret_key")
    claude = object_mapping(read_json(root / ".claude" / "settings.local.json").get("env")).get(
        "LANGFUSE_SECRET_KEY"
    )
    return isinstance(codex, str) and bool(codex) and codex == claude


def _codex_ready(root: Path, state: dict[str, object]) -> bool:
    config = read_json(root / ".codex" / "langfuse.json")
    capture_limit = state.get("max_capture_chars")
    return (
        state.get("codex_revision") == CODEX_REVISION
        and config.get("enabled") is True
        and _has_text(config, "public_key")
        and _has_text(config, "secret_key")
        and _has_text(config, "base_url")
        and config.get("base_url") == state.get("langfuse_base_url")
        and config.get("public_key") == state.get("langfuse_public_key")
        and isinstance(capture_limit, int)
        and not isinstance(capture_limit, bool)
        and config.get("max_chars") == capture_limit
        and codex_hook_is_configured(
            read_json(root / ".codex" / "hooks.json"),
            codex_hook_group(root, CODEX_REVISION),
        )
        and _revision_matches(
            root / ".agent-observability" / f"codex-plugin-{CODEX_REVISION}",
            CODEX_REVISION,
        )
    )


def _claude_ready(root: Path, state: dict[str, object]) -> bool:
    settings = read_json(root / ".claude" / "settings.local.json")
    environment = object_mapping(settings.get("env"))
    plugins = object_mapping(settings.get("enabledPlugins"))
    capture_limit = state.get("max_capture_chars")
    return (
        state.get("claude_revision") == CLAUDE_REVISION
        and _has_text(environment, "LANGFUSE_PUBLIC_KEY")
        and _has_text(environment, "LANGFUSE_SECRET_KEY")
        and _has_text(environment, "LANGFUSE_BASE_URL")
        and environment.get("LANGFUSE_BASE_URL") == state.get("langfuse_base_url")
        and environment.get("LANGFUSE_PUBLIC_KEY") == state.get("langfuse_public_key")
        and environment.get("CC_LANGFUSE_CAPTURE_SKILL_CONTENT") == "true"
        and isinstance(capture_limit, int)
        and not isinstance(capture_limit, bool)
        and environment.get("CC_LANGFUSE_MAX_CHARS") == str(capture_limit)
        and plugins.get(CLAUDE_PLUGIN) is True
        and _revision_matches(
            root / ".agent-observability" / f"claude-plugin-{CLAUDE_REVISION}",
            CLAUDE_REVISION,
        )
        and _claude_plugin_is_enabled(root)
        and claude_marketplace_status(root)[1]
    )


def status(root: Path) -> int:
    state = read_json(root / ".agent-observability" / "install.json")
    managed = _managed_agents(state)
    available = 0
    failed = not _managed_secrets_match(root, managed)
    if failed:
        print("Shared Langfuse project: managed agent credentials differ")
    for command, label, readiness in (
        ("codex", "Codex", _codex_ready),
        ("claude", "Claude Code", _claude_ready),
    ):
        if shutil.which(command) is None:
            if command in managed:
                failed = True
                print(f"{label}: configured agent is no longer installed")
            else:
                print(f"{label}: agent not installed")
            continue
        if command not in managed:
            print(f"{label}: not managed by this project")
            continue
        available += 1
        ready = readiness(root, state)
        failed = failed or not ready
        print(f"{label}: {'ready' if ready else 'not configured'}")
    return 1 if failed or available == 0 else 0


def _remove_claude_external_state(root: Path, *, remove_marketplace: bool) -> None:
    plugin_present, _ = claude_plugin_status(root)
    marketplace_present = False
    if remove_marketplace:
        marketplace_present, _ = claude_marketplace_status(root)
    if plugin_present:
        _ = run_command(
            ("claude", "plugin", "uninstall", "langfuse-observability", "--scope", "local"),
            cwd=root,
        )
    if marketplace_present:
        _ = run_command(
            (
                "claude",
                "plugin",
                "marketplace",
                "remove",
                CLAUDE_MARKETPLACE,
                "--scope",
                "local",
            ),
            cwd=root,
        )


def _scrub_claude_settings(root: Path) -> None:
    path = root / ".claude" / "settings.local.json"
    settings = read_json(path)
    environment = object_mapping(settings.get("env"))
    for name in LANGFUSE_ENV_KEYS:
        _ = environment.pop(name, None)
    plugins = object_mapping(settings.get("enabledPlugins"))
    _ = plugins.pop(CLAUDE_PLUGIN, None)
    if plugins:
        settings["enabledPlugins"] = plugins
    else:
        _ = settings.pop("enabledPlugins", None)
    if environment:
        settings["env"] = environment
    else:
        _ = settings.pop("env", None)
    if settings:
        write_private_json(path, settings)
    else:
        path.unlink(missing_ok=True)


def disable(root: Path) -> int:
    state_path = root / ".agent-observability" / "install.json"
    state = read_json(state_path)
    managed = _managed_agents(state)
    if not managed:
        raise OperatorError("no project-managed agent observability installation found")
    checkouts: list[Path] = []
    if "codex" in managed:
        write_private_json(root / ".codex" / "langfuse.json", {"enabled": False})
        hooks_path = root / ".codex" / "hooks.json"
        remaining_hooks = remove_codex_hook(read_json(hooks_path))
        if remaining_hooks:
            write_private_json(hooks_path, remaining_hooks)
        else:
            hooks_path.unlink(missing_ok=True)
        checkouts.append(root / ".agent-observability" / f"codex-plugin-{CODEX_REVISION}")
    if "claude" in managed:
        _scrub_claude_settings(root)
        checkouts.append(root / ".agent-observability" / f"claude-plugin-{CLAUDE_REVISION}")
        _remove_claude_external_state(
            root,
            remove_marketplace=state.get("claude_marketplace_owned") is True,
        )
    for checkout in checkouts:
        if checkout.exists():
            shutil.rmtree(checkout)
    state_path.unlink(missing_ok=True)
    print("Project Langfuse credentials removed and project tracing disabled.")
    print("A process-level TRACE_TO_LANGFUSE=true can override the Codex project opt-out.")
    return 0
