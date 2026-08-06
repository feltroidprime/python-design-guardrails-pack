"""The manifest hook: the same drift an update refuses, read from the inside.

A Pack Update trusts `pack/manifest.json` to say what the destination was born
with. A stale manifest therefore hides local drift from the update. These tests
hold the three hash lists, the two ignored paths, the failure that one
hand-edited pack-owned file must produce, and the user-owned shim that produces
no failure at all.
"""

import json
from pathlib import Path

import pytest

from scripts.manifest_guard import (
    IGNORED_SOURCE_SUFFIX,
    MANIFEST,
    ManifestError,
    build,
    repository_root,
    verify,
    write,
)

REPOSITORY_ROOT = repository_root()
PACKAGE = "demo"
PROJECT_FILE = '[project]\nname = "demo-product"\nversion = "1.2.3"\n'


def make_tree(root: Path) -> None:
    """A minimal tree that carries one file of every ownership kind."""
    (root / "pack" / "configs").mkdir(parents=True)
    _ = (root / "pack" / "configs" / "ruff.toml").write_text(
        "line-length = 100\n", encoding="utf-8"
    )
    (root / "pack" / "scripts").mkdir()
    _ = (root / "pack" / "scripts" / "guard.py").write_text("VALUE = 1\n", encoding="utf-8")
    package_root = root / "src" / PACKAGE
    (package_root / "_foundation").mkdir(parents=True)
    _ = (package_root / "_foundation" / "router.py").write_text("VALUE = 2\n", encoding="utf-8")
    _ = (package_root / "py.typed").write_text("", encoding="utf-8")
    _ = (package_root / "composition.py").write_text("CAPABILITIES = ()\n", encoding="utf-8")
    _ = (root / "pyproject.toml").write_text(PROJECT_FILE, encoding="utf-8")
    _ = (root / "justfile").write_text("default:\n    @just --list\n", encoding="utf-8")


def test_the_manifest_holds_three_lists_and_a_version(tmp_path: Path) -> None:
    make_tree(tmp_path)

    manifest = build(tmp_path)

    assert sorted(manifest) == ["pack_version", "package", "root", "shims"]
    assert manifest["pack_version"] == "1.2.3"


def test_root_paths_are_literal_and_package_paths_are_relative(tmp_path: Path) -> None:
    make_tree(tmp_path)

    manifest = build(tmp_path)

    assert sorted(manifest["root"]) == ["pack/configs/ruff.toml", "pack/scripts/guard.py"]
    assert sorted(manifest["package"]) == ["_foundation/router.py", "py.typed"]
    assert sorted(manifest["shims"]) == ["justfile"]


def test_a_user_owned_file_inside_the_package_is_never_recorded(tmp_path: Path) -> None:
    make_tree(tmp_path)

    manifest = build(tmp_path)

    assert "composition.py" not in manifest["package"]


def test_the_manifest_never_records_itself(tmp_path: Path) -> None:
    make_tree(tmp_path)
    write(tmp_path)

    assert MANIFEST.as_posix() not in build(tmp_path)["root"]


def test_a_staged_archive_and_the_drift_backups_are_ignored(tmp_path: Path) -> None:
    # The rule is name-blind: any archive under a source package is ignored, so
    # this pack-owned test can carry the shape without carrying a file name
    # that a Terminal Project must never carry.
    archive = f"payload{IGNORED_SOURCE_SUFFIX}"
    make_tree(tmp_path)
    _ = (tmp_path / "src" / PACKAGE / archive).write_bytes(b"payload")
    (tmp_path / "pack" / ".drift" / "configs").mkdir(parents=True)
    _ = (tmp_path / "pack" / ".drift" / "configs" / "ruff.toml").write_text(
        "old\n", encoding="utf-8"
    )

    manifest = build(tmp_path)

    assert archive not in manifest["package"]
    assert not [path for path in manifest["root"] if ".drift" in path]


def test_a_freshly_written_manifest_verifies(tmp_path: Path) -> None:
    make_tree(tmp_path)
    write(tmp_path)

    assert verify(tmp_path) == []


def test_one_hand_edited_pack_owned_file_fails_the_check(tmp_path: Path) -> None:
    make_tree(tmp_path)
    write(tmp_path)

    _ = (tmp_path / "pack" / "configs" / "ruff.toml").write_text(
        "line-length = 80\n", encoding="utf-8"
    )

    assert verify(tmp_path) == [
        "root: pack/configs/ruff.toml changed since the manifest was written"
    ]


def test_reverting_the_edit_makes_the_check_pass_again(tmp_path: Path) -> None:
    make_tree(tmp_path)
    write(tmp_path)
    path = tmp_path / "pack" / "configs" / "ruff.toml"
    original = path.read_text(encoding="utf-8")

    _ = path.write_text("line-length = 80\n", encoding="utf-8")
    _ = path.write_text(original, encoding="utf-8")

    assert verify(tmp_path) == []


def test_a_customised_shim_is_not_a_disagreement(tmp_path: Path) -> None:
    # A shim is user-owned. Its owner is invited to edit it, and Terminal
    # Projection overlays one of the four with a copy of its own, so the
    # recorded hash is history rather than a claim about the current tree.
    make_tree(tmp_path)
    write(tmp_path)

    _ = (tmp_path / "justfile").write_text("default:\n    @echo mine\n", encoding="utf-8")

    assert verify(tmp_path) == []


def test_a_new_pack_owned_file_fails_the_check(tmp_path: Path) -> None:
    make_tree(tmp_path)
    write(tmp_path)

    _ = (tmp_path / "pack" / "scripts" / "extra.py").write_text("VALUE = 3\n", encoding="utf-8")

    assert verify(tmp_path) == ["root: pack/scripts/extra.py is present but unrecorded"]


def test_a_deleted_pack_owned_file_fails_the_check(tmp_path: Path) -> None:
    make_tree(tmp_path)
    write(tmp_path)

    (tmp_path / "pack" / "scripts" / "guard.py").unlink()

    assert verify(tmp_path) == ["root: pack/scripts/guard.py is recorded but absent"]


def test_a_missing_manifest_is_reported_not_ignored(tmp_path: Path) -> None:
    make_tree(tmp_path)

    with pytest.raises(ManifestError):
        _ = verify(tmp_path)


def test_a_manifest_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    make_tree(tmp_path)
    _ = (tmp_path / MANIFEST).write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ManifestError):
        _ = verify(tmp_path)


def test_this_repository_records_its_own_gate_definition() -> None:
    manifest = build(REPOSITORY_ROOT)

    assert "pack/configs/prek.toml" in manifest["root"]
