"""Copier update round-trip acceptance test."""

import os
from pathlib import Path
import subprocess

from copier import run_copy, run_update

import instantiate


REPO_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_RELEASE = "v0.1.0"
# The candidate tag this test plants on the cloned HEAD. It must sort above
# every real release tag, or `copier check-update` reports the newest real tag
# as a pending update and the round-trip never converges. Bump it after each
# release, together with the root project version.
CURRENT_RELEASE_CANDIDATE = "v0.3.1"
RECIPE_BASE_RELEASE = "v1.2.3"
RECIPE_NEXT_RELEASE = "v1.2.4"
PROJECT_NAME = "roundtrip-project"
PACKAGE_NAME = "roundtrip_project"


def run(
    command: list[str], cwd: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def commit_all(repository: Path, message: str, environment: dict[str, str]) -> None:
    assert run(["git", "add", "--all"], repository, environment).returncode == 0
    committed = run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "commit",
            "--quiet",
            f"--message={message}",
        ],
        repository,
        environment,
    )
    assert committed.returncode == 0, committed.stdout + committed.stderr


def check_update(repository: Path, environment: dict[str, str]) -> int:
    return run(
        ["copier", "check-update", "--quiet"], repository, environment
    ).returncode


def test_previous_release_updates_cleanly_to_current_ref(tmp_path: Path) -> None:
    environment = instantiate.environment_without_local_git_context()
    template = tmp_path / "template"
    cloned = run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(template)],
        tmp_path,
        environment,
    )
    assert cloned.returncode == 0, cloned.stdout + cloned.stderr
    assert run(
        ["git", "rev-parse", "--verify", PREVIOUS_RELEASE], template, environment
    ).returncode == 0
    tagged = run(
        [
            "git",
            "-c",
            "user.name=tests",
            "-c",
            "user.email=tests@localhost",
            "tag",
            "--annotate",
            CURRENT_RELEASE_CANDIDATE,
            "--message=current release candidate",
        ],
        template,
        environment,
    )
    assert tagged.returncode == 0, tagged.stdout + tagged.stderr

    project = tmp_path / PROJECT_NAME
    with instantiate.without_local_git_context():
        run_copy(
            str(template),
            project,
            data={"project_name": PROJECT_NAME, "package": PACKAGE_NAME},
            vcs_ref=PREVIOUS_RELEASE,
            defaults=True,
            quiet=True,
            skip_tasks=True,
        )
    initialized = run(
        ["git", "init", "--quiet", "--initial-branch=main"], project, environment
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    commit_all(project, "Generate from previous release", environment)
    answers_before = (project / ".copier-answers.yml").read_text(encoding="utf-8")

    assert check_update(project, environment) == 2
    with instantiate.without_local_git_context():
        run_update(
            project,
            vcs_ref="HEAD",
            defaults=True,
            quiet=True,
            overwrite=True,
            conflict="inline",
            skip_tasks=True,
        )

    unmerged = run(
        ["git", "diff", "--name-only", "--diff-filter=U"], project, environment
    )
    assert unmerged.returncode == 0 and unmerged.stdout == ""
    assert "<<<<<<< " not in (project / "README.md").read_text(encoding="utf-8")
    diff_check = run(["git", "diff", "--check"], project, environment)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr

    answers_after = (project / ".copier-answers.yml").read_text(encoding="utf-8")
    for answer in (f"project_name: {PROJECT_NAME}", f"package: {PACKAGE_NAME}"):
        assert answer in answers_before
        assert answer in answers_after
    assert f"_commit: {PREVIOUS_RELEASE}" in answers_before
    assert f"_commit: {CURRENT_RELEASE_CANDIDATE}" in answers_after
    assert "copier check-update --quiet" in (project / "README.md").read_text(
        encoding="utf-8"
    )

    commit_all(project, "Update to current template ref", environment)
    assert run(["git", "status", "--porcelain"], project, environment).stdout == ""
    assert check_update(project, environment) == 0

    if os.environ.get("PACK_RUN_DOWNSTREAM_GATE") == "1":
        offline_environment = {
            **environment,
            "UV_OFFLINE": "1",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "",
        }
        synced = run(
            ["uv", "sync", "--all-groups", "--offline"],
            project,
            offline_environment,
        )
        assert synced.returncode == 0, synced.stdout + synced.stderr
        gate = run(
            ["uv", "run", "--offline", "python", "scripts/quality_gate.py"],
            project,
            offline_environment,
        )
        assert gate.returncode == 0, gate.stdout + gate.stderr


def test_generated_recipe_updates_from_its_recorded_git_source(tmp_path: Path) -> None:
    environment = instantiate.environment_without_local_git_context()
    template = tmp_path / "template"
    cloned = run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(template)],
        tmp_path,
        environment,
    )
    assert cloned.returncode == 0, cloned.stdout + cloned.stderr
    tagged_base = run(["git", "tag", RECIPE_BASE_RELEASE], template, environment)
    assert tagged_base.returncode == 0, tagged_base.stdout + tagged_base.stderr

    project = tmp_path / "recipe-project"
    with instantiate.without_local_git_context():
        run_copy(
            str(template),
            project,
            data={
                "project_name": PROJECT_NAME,
                "package": PACKAGE_NAME,
                "_packaged_template_source": str(template),
            },
            vcs_ref=RECIPE_BASE_RELEASE,
            defaults=True,
            quiet=True,
            skip_tasks=True,
        )
    initialized = run(
        ["git", "init", "--quiet", "--initial-branch=main"], project, environment
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    commit_all(project, "Generate recipe update project", environment)

    marker = template / "template" / "scaffold-update-proof.txt"
    marker.write_text("updated through just scaffold-update\n", encoding="utf-8")
    commit_all(template, "Add scaffold update proof", environment)
    tagged_next = run(["git", "tag", RECIPE_NEXT_RELEASE], template, environment)
    assert tagged_next.returncode == 0, tagged_next.stdout + tagged_next.stderr

    updated = run(["just", "scaffold-update"], project, environment)
    assert updated.returncode == 0, updated.stdout + updated.stderr
    assert (project / "scaffold-update-proof.txt").read_text(encoding="utf-8") == (
        "updated through just scaffold-update\n"
    )
    assert not (project / ".venv").exists()
    answers = (project / ".copier-answers.yml").read_text(encoding="utf-8")
    assert f"_commit: {RECIPE_NEXT_RELEASE}" in answers
    assert f"_src_path: {template}" in answers
    assert check_update(project, environment) == 0
