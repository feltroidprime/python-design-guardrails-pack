from pathlib import Path

import pytest

from scripts.ownership import (
    AbsolutePathError,
    ParentPathError,
    classify_path,
    matching_zones,
)
from scripts.ownership_policy import OwnershipPolicy, ZoneRoots, load_ownership_policy

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".basedpyright",
        ".codebase-memory",
        ".git",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "dist",
        "htmlcov",
    }
)
IGNORED_FILE_NAMES = frozenset({".coverage", "coverage.xml"})


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def zone(policy: OwnershipPolicy, name: str) -> ZoneRoots:
    return next(candidate for candidate in policy.zones if candidate.name == name)


def generated_files(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if (
            path.is_file()
            and not (set(relative.parts) & IGNORED_DIRECTORY_NAMES)
            and relative.name not in IGNORED_FILE_NAMES
        ):
            paths.append(relative)
    return tuple(sorted(paths))


def test_root_table_declares_the_four_ownership_zones() -> None:
    policy = load_ownership_policy(repository_root())

    assert policy.source == repository_root() / "architecture.toml"
    assert len(policy.zones) == 4
    assert len({candidate.name for candidate in policy.zones}) == len(policy.zones)


def test_classifies_a_path_from_each_declared_zone() -> None:
    policy = load_ownership_policy(repository_root())

    for candidate in policy.zones:
        root = zone(policy, candidate.name).roots[0]
        assert str(classify_path(Path(root), policy)) == candidate.name


def test_rejects_an_absolute_path() -> None:
    policy = load_ownership_policy(repository_root())

    with pytest.raises(AbsolutePathError):
        _ = classify_path(Path("/outside-the-repository"), policy)


def test_rejects_a_parent_path_escape() -> None:
    policy = load_ownership_policy(repository_root())

    with pytest.raises(ParentPathError):
        _ = classify_path(Path("scripts/../outside-the-repository"), policy)


def test_every_real_generated_file_resolves_to_exactly_one_zone() -> None:
    root = repository_root()
    policy = load_ownership_policy(root)
    paths = generated_files(root)

    assert paths
    for path in paths:
        zones = matching_zones(path, policy)
        assert len(zones) == 1, f"{path} resolves to {zones}"
        assert classify_path(path, policy) == zones[0]
