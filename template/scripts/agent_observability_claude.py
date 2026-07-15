"""Project-local Claude Code Langfuse plugin lifecycle."""

import hashlib
from pathlib import Path

from scripts.agent_observability_support import (
    Credentials,
    OperatorError,
    json_value,
    object_list,
    object_mapping,
    pinned_checkout,
    read_json,
    require_version,
    run_command,
    write_private_json,
)

CLAUDE_REPOSITORY = "https://github.com/langfuse/Claude-Observability-Plugin.git"
CLAUDE_REVISION = "3f301f3840c975bdbd16b8140140d139f27aa99b"
CLAUDE_MARKETPLACE = "langfuse-observability"
CLAUDE_PLUGIN = "langfuse-observability@langfuse-observability"
LANGFUSE_ENV_KEYS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "CC_LANGFUSE_CAPTURE_SKILL_CONTENT",
    "CC_LANGFUSE_MAX_CHARS",
)


def configure_claude(
    root: Path,
    credentials: Credentials,
    capture_limit: int,
) -> None:
    path = root / ".claude" / "settings.local.json"
    settings = read_json(path)
    environment = object_mapping(settings.get("env"))
    environment.update(
        {
            "CC_LANGFUSE_CAPTURE_SKILL_CONTENT": "true",
            "CC_LANGFUSE_MAX_CHARS": str(capture_limit),
            "LANGFUSE_BASE_URL": credentials.base_url,
            "LANGFUSE_PUBLIC_KEY": credentials.public_key,
            "LANGFUSE_SECRET_KEY": credentials.secret_key,
        }
    )
    plugins = object_mapping(settings.get("enabledPlugins"))
    plugins[CLAUDE_PLUGIN] = True
    settings["enabledPlugins"] = plugins
    settings["env"] = environment
    write_private_json(path, settings)


def _same_regular_file(source: Path, target: Path) -> bool:
    if source.is_symlink() or target.is_symlink() or not source.is_file() or not target.is_file():
        return False
    try:
        with source.open("rb") as source_stream, target.open("rb") as target_stream:
            source_hash = hashlib.file_digest(source_stream, "sha256").digest()
            target_hash = hashlib.file_digest(target_stream, "sha256").digest()
    except OSError:
        return False
    return source_hash == target_hash


def _installed_inventory_matches(installed: Path, tracked: set[Path]) -> bool:
    try:
        for candidate in installed.rglob("*"):
            if candidate.is_symlink():
                return False
            if candidate.is_file():
                relative = candidate.relative_to(installed)
                if relative not in tracked:
                    return False
    except OSError:
        return False
    return True


def _installed_tree_matches(checkout: Path, installed: Path) -> bool:
    manifest = run_command(("git", "ls-files", "-z"), cwd=checkout, check=False)
    if manifest.returncode != 0:
        return False
    tracked = {Path(item) for item in manifest.stdout.split("\0") if item}
    if not tracked or not installed.is_dir():
        return False
    tracked_files_match = all(
        _same_regular_file(checkout / relative, installed / relative) for relative in tracked
    )
    return tracked_files_match and _installed_inventory_matches(installed, tracked)


def claude_plugin_status(
    root: Path,
    reviewed_checkout: Path | None = None,
) -> tuple[bool, bool]:
    result = run_command(("claude", "plugin", "list", "--json"), cwd=root)
    entries = (
        entry
        for entry in object_list(json_value(result.stdout))
        if entry.get("id") == CLAUDE_PLUGIN and entry.get("scope") == "local"
    )
    entry = next(entries, None)
    ready = entry is not None and entry.get("enabled") is True
    if entry is not None and ready and reviewed_checkout is not None:
        raw_install_path = entry.get("installPath")
        ready = isinstance(raw_install_path, str) and _installed_tree_matches(
            reviewed_checkout,
            Path(raw_install_path).expanduser().resolve(),
        )
    return entry is not None, ready


def claude_marketplace_status(root: Path) -> tuple[bool, bool]:
    result = run_command(("claude", "plugin", "marketplace", "list", "--json"), cwd=root)
    entries = [
        entry
        for entry in object_list(json_value(result.stdout))
        if entry.get("name") == CLAUDE_MARKETPLACE
    ]
    exact_revision = False
    for entry in entries:
        raw_path = entry.get("path") or entry.get("installLocation")
        if not isinstance(raw_path, str):
            continue
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            continue
        revision = run_command(("git", "rev-parse", "HEAD"), cwd=path, check=False)
        cleanliness = run_command(
            ("git", "status", "--porcelain"),
            cwd=path,
            check=False,
        )
        exact_revision = exact_revision or (
            revision.returncode == 0
            and revision.stdout.strip() == CLAUDE_REVISION
            and cleanliness.returncode == 0
            and not cleanliness.stdout.strip()
        )
    return bool(entries), exact_revision


def claude_configuration_present(root: Path) -> bool:
    settings = read_json(root / ".claude" / "settings.local.json")
    environment = object_mapping(settings.get("env"))
    plugins = object_mapping(settings.get("enabledPlugins"))
    plugin_present, _ = claude_plugin_status(root)
    return (
        plugin_present
        or CLAUDE_PLUGIN in plugins
        or any(name in environment for name in LANGFUSE_ENV_KEYS)
    )


def install_claude(
    root: Path,
    credentials: Credentials,
    capture_limit: int,
    *,
    marketplace_owned: bool,
    replace_existing: bool,
) -> None:
    require_version("claude", (2, 0, 0), root)
    checkout = pinned_checkout(
        root,
        agent="claude",
        repository=CLAUDE_REPOSITORY,
        revision=CLAUDE_REVISION,
    )
    if replace_existing:
        _ = run_command(
            ("claude", "plugin", "uninstall", "langfuse-observability", "--scope", "local"),
            cwd=root,
            check=False,
        )
    if replace_existing and marketplace_owned:
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
            check=False,
        )
    if marketplace_owned:
        _ = run_command(
            ("claude", "plugin", "marketplace", "add", str(checkout), "--scope", "local"),
            cwd=root,
        )
    _ = run_command(("claude", "plugin", "install", CLAUDE_PLUGIN, "--scope", "local"), cwd=root)
    configure_claude(root, credentials, capture_limit)
    _, ready = claude_plugin_status(root, checkout)
    if not ready:
        raise OperatorError("installed Claude plugin differs from the reviewed checkout")
