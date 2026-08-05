"""A small pack tree, and the two things the tests drive it with.

The tests build a pack of nine files rather than the real tree. The nine files
carry every shape the projection has to answer: both identity tokens in file
content, both path components that equal a token, the three starting files, and
the capability directory itself. A small tree makes each assertion readable and
each run fast, and the whole real tree is what the acceptance suite of #81
measures from the installed console script.

`fake_pack` writes that tree. `Recorder` is a `CommandRunner` that records the
commands instead of running them, so an ordering test never starts a process.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
import subprocess
import tarfile
from types import MappingProxyType

import pytest

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
    """Write one whole tree from a map of relative locations to text."""
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

    @property
    def programs(self) -> tuple[str, ...]:
        """The program of each recorded command, in order."""
        return tuple(command[0] for command in self.commands)
