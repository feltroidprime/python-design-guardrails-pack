"""The gate definition: twelve hooks, and a Pack-owned Surface with no name.

`pack/configs/prek.toml` is the one gate of the tree. A pack update replaces it
whole, so it must carry no identity token. The same holds for every other
pack-owned file: an update that carried a name would write one project's
identity into another project.

The two identity values come from `pyproject.toml`, so this file states neither
of them and needs no exemption from its own scan.
"""

from pathlib import Path
import subprocess
import tomllib
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATE = Path("pack/configs/prek.toml")
PROJECT_FILE = "pyproject.toml"
TRACKED_NAMES_COMMAND = ("git", "ls-files", "-z", "--cached", "--exclude-standard", "--", "pack")
TWELVE_HOOKS = frozenset(
    {
        "lockfile",
        "format",
        "lint",
        "types",
        "dependencies",
        "architecture",
        "docs",
        "proof",
        "symbolic",
        "import-contracts",
        "tests",
        "manifest",
    }
)


def load(path: Path) -> dict[str, object]:
    return cast("dict[str, object]", tomllib.loads(path.read_text(encoding="utf-8")))


def table(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def text(value: object) -> str:
    assert isinstance(value, str)
    return value


def items(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast("list[object]", value)


def local_hook_ids(root: Path) -> set[str]:
    """Every hook id that the gate defines locally."""
    repositories = [table(entry) for entry in items(load(root / GATE)["repos"])]
    return {
        text(table(hook)["id"])
        for repository in repositories
        if repository["repo"] == "local"
        for hook in items(repository["hooks"])
    }


def identity_tokens(root: Path) -> tuple[str, ...]:
    """The distribution name and the import package name of this tree."""
    project = load(root / PROJECT_FILE)
    build_backend = table(table(table(project["tool"])["uv"])["build-backend"])
    return (
        text(table(project["project"])["name"]),
        text(build_backend["module-name"]),
    )


def tracked_pack_files(root: Path) -> tuple[Path, ...]:
    completed = subprocess.run(  # noqa: S603  # ARCH-EXCEPTION: ADR-0007
        TRACKED_NAMES_COMMAND,
        cwd=root,
        capture_output=True,
        check=True,
    )
    return tuple(root / raw.decode() for raw in completed.stdout.split(b"\0") if raw)


def test_the_gate_is_exactly_twelve_local_hooks() -> None:
    assert local_hook_ids(REPOSITORY_ROOT) == TWELVE_HOOKS


def test_no_pack_owned_file_carries_an_identity_token() -> None:
    tokens = identity_tokens(REPOSITORY_ROOT)
    found = [
        f"{path.relative_to(REPOSITORY_ROOT)}: {token}"
        for path in tracked_pack_files(REPOSITORY_ROOT)
        for token in tokens
        if token in path.read_text(encoding="utf-8", errors="ignore")
    ]

    assert tokens
    assert found == []
