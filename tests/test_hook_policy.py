"""Contract tests for the pack's local hook routing."""

from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
JUSTFILE = REPO_ROOT / "justfile"
QUALITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "quality.yml"
RECURSIVE_ACCEPTANCE = (
    "tests/recursive/test_recursive_generation.py"
    "::test_recursive_walk_executes_the_specification_through_repoctl"
)


def local_hooks() -> dict[str, dict[str, object]]:
    """Return root local hooks by identifier."""
    config = tomllib.loads((REPO_ROOT / "prek.toml").read_text(encoding="utf-8"))
    return {
        hook["id"]: hook
        for repository in config["repos"]
        if repository["repo"] == "local"
        for hook in repository["hooks"]
    }


def test_pre_commit_is_fast_pre_push_is_bounded_and_ci_is_comprehensive() -> None:
    hooks = local_hooks()
    justfile = JUSTFILE.read_text(encoding="utf-8")
    workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")

    assert hooks["pack-fast"]["entry"] == "just test-fast"
    assert hooks["pack-fast"]["stages"] == ["pre-commit"]
    assert hooks["pack-push"]["entry"] == "just test"
    assert hooks["pack-push"]["name"] == "pack push checks (full root suite, <7m warm)"
    assert hooks["pack-push"]["stages"] == ["pre-push"]
    assert justfile.count(RECURSIVE_ACCEPTANCE) == 1
    solo = "{{root_pytest}} -q {{recursive_acceptance}}"
    heavyweight = (
        "{{root_pytest}} -q -n 5 --dist worksteal -m {{repository_gate_marker}} "
        "tests --deselect {{recursive_acceptance}}"
    )
    lightweight = (
        '{{root_pytest}} -q -n 5 --dist worksteal -m "not {{repository_gate_marker}}" '
        "tests --deselect {{recursive_acceptance}}"
    )
    assert justfile.index(solo) < justfile.index(heavyweight) < justfile.index(lightweight)
    assert "run: just validate" in workflow


def test_hooks_recipe_provisions_a_durable_prek_executable() -> None:
    recipe = JUSTFILE.read_text(encoding="utf-8")

    assert 'uv tool install "prek>=0.4.9"' in recipe
    assert "prek install -f" in recipe
