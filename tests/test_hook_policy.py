"""Contract tests for the pack's local hook routing."""

from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]


def local_hooks() -> dict[str, dict[str, object]]:
    """Return root local hooks by identifier."""
    config = tomllib.loads((REPO_ROOT / "prek.toml").read_text(encoding="utf-8"))
    return {
        hook["id"]: hook
        for repository in config["repos"]
        if repository["repo"] == "local"
        for hook in repository["hooks"]
    }


def test_pre_commit_is_fast_and_pre_push_remains_comprehensive() -> None:
    hooks = local_hooks()

    assert hooks["pack-fast"]["entry"] == "just test-fast"
    assert hooks["pack-validate"]["entry"] == "just validate"
    assert hooks["pack-validate"]["stages"] == ["pre-push"]
