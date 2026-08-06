"""A small pack tree, a small project tree, and the things the tests drive them with.

The tests build a pack of nine files rather than the real tree. The nine files
carry every shape the projection has to answer: both identity tokens in file
content, both path components that equal a token, the three starting files, and
the capability directory itself. A small tree makes each assertion readable and
each run fast, and the whole real tree is what the acceptance suite measures
from the installed console script.

`fake_pack` writes that tree. `Recorder` is a `CommandRunner` that records the
commands instead of running them, so an ordering test never starts a process.

The update fixtures below write two more trees: one release of a pack, and one
project born from a release. Both write their own `pack/manifest.json` from the
same mappings they wrote the files from, so a fixture record never comes from
the code the update tests measure. Every pack-owned file here is name-blind, so
the record of the pack is the record of the project.
"""

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tarfile
from types import MappingProxyType
from typing import override

import pytest

STATUS_ARGUMENT = "status"
PACK_PROJECT = "pyrepo"
PACK_PACKAGE = "guardrails_pack"
CAPABILITY = "bootstrap"

PROJECT_FILE = f"""[project]
name = "{PACK_PROJECT}"
version = "0.3.0"

[project.scripts]
{PACK_PROJECT} = "{PACK_PACKAGE}.cli:main"

[tool.uv.build-backend]
module-name = "{PACK_PACKAGE}"
"""

PACK_TREE: Mapping[str, str] = MappingProxyType(
    {
        "pyproject.toml": PROJECT_FILE,
        "README.md": f"# {PACK_PROJECT}\n\nThe pack itself.\n",
        "CHANGELOG.md": f"# {PACK_PROJECT} changelog\n\n## [0.3.0]\n",
        "pack/justfile": f"check:\n    uv run {PACK_PROJECT} --help\n",
        f"src/{PACK_PACKAGE}/cli.py": f"from {PACK_PACKAGE}._foundation.router import main\n",
        f"src/{PACK_PACKAGE}/composition.py": (
            f"from {PACK_PACKAGE}.{CAPABILITY} import api\n\nCAPABILITIES = (api,)\n"
        ),
        f"src/{PACK_PACKAGE}/{CAPABILITY}/api.py": "def init() -> None:\n    return None\n",
        f"src/{PACK_PACKAGE}/{CAPABILITY}/initial/README.md": f"# {PACK_PROJECT}\n\nYour product.\n",
        f"src/{PACK_PACKAGE}/{CAPABILITY}/initial/CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n",
        f"src/{PACK_PACKAGE}/{CAPABILITY}/initial/src/{PACK_PACKAGE}/composition.py": (
            "CAPABILITIES = ()\n"
        ),
    }
)


def write_tree(root: Path, contents: Mapping[str, str]) -> Path:
    """Write one whole tree from a map of relative paths to text."""
    for relative, text in contents.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def fake_pack(tmp_path: Path) -> Path:
    """A nine-file pack tree, with both tokens in content and in path components."""
    return write_tree(tmp_path / "pack-tree", dict(PACK_TREE))


def build_archive(tree: Path, archive: Path) -> Path:
    """Pack one tree into a tar, the way a release stages the payload."""
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w") as opened:
        for entry in sorted(tree.rglob("*")):
            opened.add(entry, arcname=entry.relative_to(tree).as_posix())
    return archive


def git(tree: Path, *arguments: str) -> None:
    """Run one git command in *tree*, with a repository-local identity."""
    _ = subprocess.run(["git", *arguments], cwd=tree, check=True, capture_output=True)


def commit_tree(tree: Path) -> Path:
    """Turn one tree into a git checkout with exactly one commit."""
    git(tree, "init", "--quiet", "--initial-branch=main")
    git(tree, "config", "user.email", "test@localhost")
    git(tree, "config", "user.name", "Test")
    git(tree, "add", "--all")
    git(tree, "commit", "--quiet", "--message", "Pack")
    return tree


class Recorder:
    """A `CommandRunner` that records every command and starts no process."""

    def __init__(self, *, failing: str = "", present: bool = True) -> None:
        """Record commands. *failing* names the program whose run must fail."""
        self.commands: list[tuple[str, ...]] = []
        self.failing: str = failing
        self.present: bool = present

    def run(self, command: Sequence[str], directory: Path, /) -> None:
        """Record one command, and raise `OSError` when it is the failing one."""
        self.commands.append(tuple(command))
        if self.failing and command[0] == self.failing:
            raise OSError(f"'{self.failing}' ended with 1 in '{directory}'.")

    def succeeds(self, command: Sequence[str], _directory: Path, /) -> bool:
        """Record one probe and report the configured answer."""
        self.commands.append(tuple(command))
        return self.present

    def read(self, command: Sequence[str], _directory: Path, /) -> str:
        """Record one reading command and report no output."""
        self.commands.append(tuple(command))
        return ""

    @property
    def programs(self) -> tuple[str, ...]:
        """The program of each recorded command, in order."""
        return tuple(command[0] for command in self.commands)


class Worktree(Recorder):
    """A `Recorder` that answers the two git readings of refusal `U4`."""

    @override
    def __init__(self, *, present: bool = True, dirty: str = "") -> None:
        """Report the destination as a repository, and *dirty* as its status."""
        super().__init__(present=present)
        self.dirty: str = dirty

    @override
    def read(self, command: Sequence[str], directory: Path, /) -> str:
        """Give the status of the worktree, or the root the destination sits in."""
        self.commands.append(tuple(command))
        return self.dirty if STATUS_ARGUMENT in command else f"{directory}\n"


# --- The two trees of a Pack Update -------------------------------------------

PROJECT_PROJECT = "my-product"
PROJECT_PACKAGE = "my_product"
MANIFEST = "pack/manifest.json"

# The Pack-owned Surface of the fixture, in the two shapes the manifest holds.
# No entry carries an identity token, so the same bytes stand in both trees.
PACK_ROOT_SURFACE: Mapping[str, str] = MappingProxyType(
    {
        "pack/.gitignore": ".drift/\n",
        "pack/configs/ruff.toml": "line-length = 100\n",
        "pack/justfile": "check:\n    prek run --all-files\n",
        "pack/scripts/guard.py": '"""One pack-owned guard."""\n',
    }
)
PACK_PACKAGE_SURFACE: Mapping[str, str] = MappingProxyType(
    {
        "_foundation/router.py": '"""The router."""\n',
        "py.typed": "",
    }
)
# The user-owned entry points. The manifest records their as-shipped bytes and
# an update never writes one of them.
SHIM_CONTENTS: Mapping[str, str] = MappingProxyType(
    {
        ".github/workflows/quality.yml": "name: quality\n",
        ".python-version": "3.14\n",
        "justfile": "import 'pack/justfile'\n",
        "pyrightconfig.json": '{"extends": "pack/configs/pyrightconfig.json"}\n',
    }
)


def digest_of(path: Path) -> str:
    """The sha256 of one file, written here so no fixture reads production code."""
    return sha256(path.read_bytes()).hexdigest()


def user_contents(name: str, package: str) -> dict[str, str]:
    """The user-owned files of one tree: identity, prose, and one capability."""
    return {
        "pyproject.toml": f'[project]\nname = "{name}"\n',
        "README.md": f"# {name}\n",
        "CHANGELOG.md": f"# {name} changelog\n",
        f"src/{package}/cli.py": f"from {package}._foundation.router import main\n",
        f"src/{package}/composition.py": "CAPABILITIES = ()\n",
        f"src/{package}/billing/api.py": '"""Bill a customer."""\n',
        **SHIM_CONTENTS,
    }


def write_manifest(
    tree: Path,
    package: str,
    version: str,
    surface: tuple[Mapping[str, str], Mapping[str, str]],
) -> Path:
    """Write the record of one tree from the mappings that tree was written from."""
    root_surface, package_surface = surface
    record = {
        "pack_version": version,
        "root": {relative: digest_of(tree / relative) for relative in sorted(root_surface)},
        "package": {
            relative: digest_of(tree / "src" / package / relative)
            for relative in sorted(package_surface)
        },
        "shims": {relative: digest_of(tree / relative) for relative in sorted(SHIM_CONTENTS)},
    }
    target = tree / MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def write_release(
    root: Path,
    version: str,
    *,
    root_surface: Mapping[str, str] = PACK_ROOT_SURFACE,
    package_surface: Mapping[str, str] = PACK_PACKAGE_SURFACE,
) -> Path:
    """One Root Pack at *version*, capability directory and manifest included."""
    contents = {
        **user_contents(PACK_PROJECT, PACK_PACKAGE),
        **root_surface,
        **{f"src/{PACK_PACKAGE}/{name}": text for name, text in package_surface.items()},
        f"src/{PACK_PACKAGE}/{CAPABILITY}/api.py": '"""Project this pack."""\n',
    }
    _ = write_tree(root, contents)
    _ = write_manifest(root, PACK_PACKAGE, version, (root_surface, package_surface))
    return root


def write_destination(
    root: Path,
    version: str,
    *,
    root_surface: Mapping[str, str] = PACK_ROOT_SURFACE,
    package_surface: Mapping[str, str] = PACK_PACKAGE_SURFACE,
) -> Path:
    """One committed Terminal Project born from the release at *version*."""
    contents = {
        **user_contents(PROJECT_PROJECT, PROJECT_PACKAGE),
        **root_surface,
        **{f"src/{PROJECT_PACKAGE}/{name}": text for name, text in package_surface.items()},
    }
    _ = write_tree(root, contents)
    _ = write_manifest(root, PROJECT_PACKAGE, version, (root_surface, package_surface))
    return commit_tree(root)
