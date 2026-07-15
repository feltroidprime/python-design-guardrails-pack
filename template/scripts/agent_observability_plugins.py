"""Pinned coding-agent plugin installation and local Langfuse configuration."""

import os
import shutil
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

from scripts.agent_observability_claude import (
    CLAUDE_REVISION,
    claude_configuration_present,
    claude_marketplace_status,
    configure_claude,
    install_claude,
)
from scripts.agent_observability_codex_hook import codex_hook_group, merge_codex_hook
from scripts.agent_observability_support import (
    Credentials,
    OperatorError,
    object_mapping,
    pinned_checkout,
    read_json,
    require_version,
    write_private_json,
)

if TYPE_CHECKING:
    from pathlib import Path

CODEX_REPOSITORY = "https://github.com/langfuse/codex-observability-plugin.git"
CODEX_REVISION = "33bc50ba75ef82ed1f3718df6fdd06cdbfc7c02e"
DEFAULT_MAX_CAPTURE_CHARS = 2_147_483_647


def _answers(root: Path) -> tuple[str, str]:
    values: dict[str, str] = {}
    path = root / ".copier-answers.yml"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, raw = line.partition(":")
            if separator and name in {"_commit", "project_name"}:
                values[name] = raw.strip().strip("'\"")
    return values.get("project_name", root.name), values.get("_commit", "unknown")


def _credentials_from_environment() -> Credentials:
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    missing = [
        name
        for name, value in (
            ("LANGFUSE_PUBLIC_KEY", public_key),
            ("LANGFUSE_SECRET_KEY", secret_key),
        )
        if not value
    ]
    if missing:
        raise OperatorError("missing credential environment variables: " + ", ".join(missing))
    return Credentials(
        public_key=public_key,
        secret_key=secret_key,
        base_url=_validated_base_url(
            os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
        ),
    )


def _max_capture_chars() -> int:
    raw = os.environ.get("AGENT_OBSERVABILITY_MAX_CHARS", str(DEFAULT_MAX_CAPTURE_CHARS))
    try:
        value = int(raw)
    except ValueError as error:
        raise OperatorError("AGENT_OBSERVABILITY_MAX_CHARS must be a positive integer") from error
    if value <= 0:
        raise OperatorError("AGENT_OBSERVABILITY_MAX_CHARS must be a positive integer")
    return value


def _validated_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OperatorError("LANGFUSE_BASE_URL must be an absolute HTTP(S) URL")
    return value.rstrip("/")


def _codex_config(root: Path, credentials: Credentials) -> dict[str, object]:
    project, template_version = _answers(root)
    return {
        "base_url": credentials.base_url,
        "enabled": True,
        "metadata": {
            "repository": project,
            "repository_root": str(root),
            "template_version": template_version,
        },
        "max_chars": _max_capture_chars(),
        "public_key": credentials.public_key,
        "secret_key": credentials.secret_key,
        "tags": ["python-design-guardrails-pack", f"repository:{project}"],
    }


def _install_codex(root: Path, credentials: Credentials) -> None:
    require_version("codex", (0, 128, 0), root)
    require_version("node", (22, 0, 0), root)
    _ = pinned_checkout(
        root,
        agent="codex",
        repository=CODEX_REPOSITORY,
        revision=CODEX_REVISION,
    )
    entrypoint = (
        root
        / ".agent-observability"
        / f"codex-plugin-{CODEX_REVISION}"
        / "plugins"
        / "tracing"
        / "dist"
        / "index.mjs"
    )
    if not entrypoint.is_file():
        raise OperatorError(f"Codex plugin entrypoint is missing: {entrypoint}")
    write_private_json(root / ".codex" / "langfuse.json", _codex_config(root, credentials))
    hooks_path = root / ".codex" / "hooks.json"
    hooks = merge_codex_hook(read_json(hooks_path), codex_hook_group(root, CODEX_REVISION))
    write_private_json(hooks_path, hooks)


def _write_install_state(
    root: Path,
    installed: list[str],
    credentials: Credentials,
    capture_limit: int,
    *,
    marketplace_owned: bool,
) -> None:
    state: dict[str, object] = {
        "agents": installed,
        "langfuse_base_url": credentials.base_url,
        "langfuse_public_key": credentials.public_key,
        "max_capture_chars": capture_limit,
    }
    if "claude" in installed:
        state["claude_revision"] = CLAUDE_REVISION
        state["claude_marketplace_owned"] = marketplace_owned
    if "codex" in installed:
        state["codex_revision"] = CODEX_REVISION
    write_private_json(root / ".agent-observability" / "install.json", state)


def _installed_agents(root: Path) -> list[str]:
    agents = read_json(root / ".agent-observability" / "install.json").get("agents")
    if not isinstance(agents, list):
        return []
    configured = {agent for agent in cast("list[object]", agents) if isinstance(agent, str)}
    return [agent for agent in ("codex", "claude") if agent in configured]


def _preflight_install(
    root: Path,
    candidates: tuple[str, ...],
    credentials: Credentials,
    capture_limit: int,
) -> tuple[list[str], bool]:
    missing = [agent for agent in candidates if shutil.which(agent) is None]
    if missing:
        absent = ", ".join(missing)
        raise OperatorError(
            f"required command missing: {absent}; set AGENT_OBSERVABILITY_AGENT explicitly"
        )
    installed = _installed_agents(root)
    state = read_json(root / ".agent-observability" / "install.json")
    if installed and state.get("max_capture_chars") != capture_limit:
        raise OperatorError(
            "AGENT_OBSERVABILITY_MAX_CHARS must match the existing project installation"
        )
    if installed and (
        state.get("langfuse_base_url") != credentials.base_url
        or state.get("langfuse_public_key") != credentials.public_key
    ):
        raise OperatorError(
            "Langfuse base URL and public key must match the existing project installation"
        )
    claude_was_managed = "claude" in installed
    marketplace_owned = state.get("claude_marketplace_owned") is True
    if "claude" in candidates and not claude_was_managed and claude_configuration_present(root):
        raise OperatorError(
            "a local Claude Langfuse configuration already exists outside project management"
        )
    if "claude" in candidates and not claude_was_managed:
        marketplace_exists, exact_revision = claude_marketplace_status(root)
        if marketplace_exists and not exact_revision:
            raise OperatorError(
                "the existing Claude Langfuse marketplace is not at the reviewed revision"
            )
        marketplace_owned = not marketplace_exists
    if "claude" in candidates and claude_was_managed and not marketplace_owned:
        _, exact_revision = claude_marketplace_status(root)
        if not exact_revision:
            raise OperatorError(
                "the reused Claude Langfuse marketplace is no longer at the reviewed revision"
            )
    return installed, marketplace_owned


def _synchronize_credentials(
    root: Path,
    installed: list[str],
    credentials: Credentials,
    capture_limit: int,
) -> None:
    if "codex" in installed:
        write_private_json(root / ".codex" / "langfuse.json", _codex_config(root, credentials))
    if "claude" in installed:
        configure_claude(root, credentials, capture_limit)


def install(root: Path, selected: str) -> int:
    credentials = _credentials_from_environment()
    capture_limit = _max_capture_chars()
    candidates = ("codex", "claude") if selected == "all" else (selected,)
    installed, marketplace_owned = _preflight_install(root, candidates, credentials, capture_limit)
    claude_was_managed = "claude" in installed
    _synchronize_credentials(root, installed, credentials, capture_limit)
    for agent in candidates:
        if agent not in installed:
            installed.append(agent)
        _write_install_state(
            root,
            installed,
            credentials,
            capture_limit,
            marketplace_owned=marketplace_owned,
        )
        if agent == "codex":
            _install_codex(root, credentials)
        else:
            install_claude(
                root,
                credentials,
                capture_limit,
                marketplace_owned=marketplace_owned,
                replace_existing=claude_was_managed,
            )
            claude_was_managed = True
        print(f"{agent}: Langfuse tracing installed")
    _synchronize_credentials(root, installed, credentials, capture_limit)
    if not installed:
        raise OperatorError("neither Codex nor Claude Code is installed")
    print("Restart each installed agent before recording a session.")
    return 0


def credentials_from_project(root: Path) -> Credentials:
    codex = read_json(root / ".codex" / "langfuse.json")
    claude = object_mapping(read_json(root / ".claude" / "settings.local.json").get("env"))
    public_key = codex.get("public_key") or claude.get("LANGFUSE_PUBLIC_KEY")
    secret_key = codex.get("secret_key") or claude.get("LANGFUSE_SECRET_KEY")
    base_url = codex.get("base_url") or claude.get("LANGFUSE_BASE_URL")
    if not isinstance(public_key, str) or not isinstance(secret_key, str):
        return _credentials_from_environment()
    return Credentials(
        public_key=public_key,
        secret_key=secret_key,
        base_url=_validated_base_url(
            base_url if isinstance(base_url, str) else "https://cloud.langfuse.com"
        ),
    )
