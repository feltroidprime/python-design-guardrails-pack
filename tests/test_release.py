"""Release-command acceptance tests."""

from pathlib import Path
import shutil
import subprocess

import instantiate


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_release_refuses_version_missing_from_changelog(tmp_path: Path) -> None:
    git_env = instantiate.environment_without_local_git_context()
    repository = tmp_path / "pack"
    (repository / "scripts").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "justfile", repository / "justfile")
    shutil.copy(REPO_ROOT / "scripts" / "release.py", repository / "scripts" / "release.py")
    (repository / "CHANGELOG.md").write_text(
        "# Template changelog\n\n## [v0.1.0]\n\n- First release.\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main"],
        cwd=repository,
        env=git_env,
        check=True,
    )
    subprocess.run(
        ["git", "add", "--all"], cwd=repository, env=git_env, check=True
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            "--message=release fixture",
        ],
        cwd=repository,
        env=git_env,
        check=True,
    )

    result = subprocess.run(
        ["just", "release", "v9.9.9"],
        cwd=repository,
        env=git_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "CHANGELOG.md has no '## [v9.9.9]' entry" in result.stdout + result.stderr
    tags = subprocess.run(
        ["git", "tag", "--list"],
        cwd=repository,
        env=git_env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tags.stdout == ""
