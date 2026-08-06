"""The order of the pipeline, the one network step, and the release step.

`init` runs `git init`, `just setup`, the first commit, then `prek install`.
`gh repo create` runs only for `--github`, and `--public` selects the
visibility. `release` stages the payload, builds the wheel, then deletes the
payload, and it deletes it even when the build fails.

Every case drives a recorder rather than a real program, so the order is what is
under test and nothing here opens a socket or writes outside `tmp_path`.
"""

from pathlib import Path

import pytest

from guardrails_pack.bootstrap.adapters.outbound.payload import InstalledPayload
from guardrails_pack.bootstrap.application.creation import (
    Request,
    create_project,
    requested_identity,
)
from guardrails_pack.bootstrap.application.release import stage_and_build
from guardrails_pack.bootstrap.tests.conftest import PACK_PACKAGE, Recorder, build_archive

PROJECT = "my-product"
ORDER = ("git", "git", "git", "git", "just", "uv")


def run_init(
    tmp_path: Path, fake_pack: Path, runner: Recorder, *, github: bool = False, public: bool = False
) -> Path:
    """One whole `init` against the recorder, and the destination it created."""
    payload = InstalledPayload(archive=build_archive(fake_pack, tmp_path / "pack.tar"))
    destination = tmp_path / "term"
    request = Request(
        project=requested_identity(PROJECT, ""),
        destination=destination,
        github=github,
        public=public,
    )
    _ = create_project(payload, runner, request)
    return destination


def test_init_runs_the_five_steps_in_order(tmp_path: Path, fake_pack: Path) -> None:
    runner = Recorder()

    destination = run_init(tmp_path, fake_pack, runner)

    assert destination.is_dir()
    assert runner.programs == ORDER
    assert runner.commands[0][:2] == ("git", "init")
    assert runner.commands[2][:2] == ("git", "add")
    assert "commit" in runner.commands[3]
    assert runner.commands[4] == ("just", "setup")
    assert runner.commands[5][:4] == ("uv", "run", "prek", "install")


def test_init_reaches_no_network_without_the_github_flag(tmp_path: Path, fake_pack: Path) -> None:
    runner = Recorder()

    _ = run_init(tmp_path, fake_pack, runner)

    assert "gh" not in runner.programs


def test_the_github_flag_creates_a_private_repository_and_pushes(
    tmp_path: Path, fake_pack: Path
) -> None:
    runner = Recorder()

    _ = run_init(tmp_path, fake_pack, runner, github=True)

    assert runner.programs == (*ORDER, "gh")
    assert runner.commands[-1] == (
        "gh",
        "repo",
        "create",
        PROJECT,
        "--private",
        "--source",
        ".",
        "--remote",
        "origin",
        "--push",
    )


def test_the_public_flag_flips_the_visibility(tmp_path: Path, fake_pack: Path) -> None:
    runner = Recorder()

    _ = run_init(tmp_path, fake_pack, runner, github=True, public=True)

    assert "--public" in runner.commands[-1]
    assert "--private" not in runner.commands[-1]


def test_a_setup_failure_stops_before_the_hooks_and_before_github(
    tmp_path: Path, fake_pack: Path
) -> None:
    runner = Recorder(failing="just")

    with pytest.raises(OSError, match="just"):
        _ = run_init(tmp_path, fake_pack, runner, github=True)

    assert runner.programs == ("git", "git", "git", "git", "just")
    assert (tmp_path / "term").is_dir()


def test_the_commit_carries_a_fallback_identity_when_the_machine_states_none(
    tmp_path: Path, fake_pack: Path
) -> None:
    runner = Recorder(present=False)

    _ = run_init(tmp_path, fake_pack, runner)

    assert "-c" in runner.commands[3]


def test_release_stages_the_payload_builds_the_wheel_then_deletes_the_payload(
    tmp_path: Path,
) -> None:
    runner = Recorder()
    root = tmp_path / "pack"
    (root / "src" / PACK_PACKAGE).mkdir(parents=True)

    result = stage_and_build(runner, root, PACK_PACKAGE, tmp_path / "dist")

    assert [command[:3] for command in runner.commands] == [
        ("git", "archive", "HEAD"),
        ("uv", "build", "--wheel"),
    ]
    assert result["staged"] is False
    assert not (root / "src" / PACK_PACKAGE / "_pack.tar").exists()


def test_release_deletes_the_payload_even_when_the_build_fails(tmp_path: Path) -> None:
    runner = Recorder(failing="uv")
    root = tmp_path / "pack"
    blob = root / "src" / PACK_PACKAGE / "_pack.tar"
    blob.parent.mkdir(parents=True)
    _ = blob.write_bytes(b"an interrupted build")

    with pytest.raises(OSError, match="uv"):
        _ = stage_and_build(runner, root, PACK_PACKAGE, tmp_path / "dist")

    assert not blob.exists()
