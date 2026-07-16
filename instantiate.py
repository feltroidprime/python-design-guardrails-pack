#!/usr/bin/env python3
"""Instantiate the repository template through Copier.

Two entry points share the same generator core:

- legacy positional form: ``python3 instantiate.py <project> <package> <output-dir>``;
- installed CLI (``python-repo`` console script): ``python-repo init <name> [directory] [--package NAME]``.
"""

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version as distribution_version
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading

from copier import run_copy
from copier.errors import CopierError
from plumbum import local

PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
DISTRIBUTION_NAME = "python-design-guardrails-pack"
TEMPLATE_SOURCE = "https://github.com/feltroidprime/python-design-guardrails-pack.git"
GIT_CONTEXT_LOCK = threading.RLock()
LOCAL_GIT_ENVIRONMENT = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)


def is_local_git_environment(key: str) -> bool:
    """Return whether *key* can bind Git commands to a caller's repository."""
    return key in LOCAL_GIT_ENVIRONMENT or key.startswith(
        ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
    )


def derive_package_name(project_name: str) -> str:
    """Best-effort import package derived from the project name."""
    return project_name.replace("-", "_").replace(".", "_")


def packaged_template_version() -> str | None:
    """Return the release tag represented by an installed wheel, when available."""
    try:
        return f"v{distribution_version(DISTRIBUTION_NAME)}"
    except PackageNotFoundError:
        return None


def environment_without_local_git_context() -> dict[str, str]:
    """Copy the process environment without a calling repository's Git context."""
    return {
        key: value
        for key, value in os.environ.items()
        if not is_local_git_environment(key)
    }


@contextmanager
def without_local_git_context() -> Iterator[None]:
    """Prevent Copier's temporary git operations from mutating a caller's index."""
    with GIT_CONTEXT_LOCK:
        inherited = {
            key: os.environ.pop(key)
            for key in tuple(os.environ)
            if is_local_git_environment(key)
        }
        try:
            with local.env():
                for key in tuple(local.env.keys()):
                    if is_local_git_environment(key):
                        local.env.pop(key)
                yield
        finally:
            os.environ.update(inherited)


def generate(project_name: str, package_name: str, output: Path) -> str | None:
    """Render the template into *output*. Return an error message, or None on success."""
    source = Path(__file__).resolve().parent
    if output.exists() and any(output.iterdir()):
        return f"Refusing to overwrite non-empty directory: {output}"
    try:
        with without_local_git_context():
            run_copy(
                str(source),
                output,
                data={
                    "project_name": project_name,
                    "package": package_name,
                    "_packaged_template_version": packaged_template_version(),
                    "_packaged_template_source": TEMPLATE_SOURCE,
                },
                vcs_ref="HEAD",
                defaults=True,
                quiet=True,
                skip_tasks=True,
            )
    except (CopierError, ValueError) as error:
        message = str(error)
        for question in ("project_name", "package"):
            prefix = f"Validation error for question '{question}': "
            if message.startswith(prefix):
                return message.removeprefix(prefix)
        return message
    return None


GIT_COMMIT_MESSAGE = "Initial commit from python-design-guardrails-pack"


def run_command(command: list[str], cwd: Path) -> str | None:
    """Run a command in *cwd*; return an error message on failure, None on success."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment_without_local_git_context(),
        check=False,
    )
    if completed.returncode != 0:
        return f"'{' '.join(command)}' exited with {completed.returncode}."
    return None


def initialize_git_repository(output: Path) -> str | None:
    """git init + initial commit. Return an error message, or None on success."""
    if shutil.which("git") is None:
        return "git was not found on PATH; cannot initialize a git repository."
    identity: list[str] = []
    email = subprocess.run(
        ["git", "config", "--get", "user.email"],
        cwd=output,
        env=environment_without_local_git_context(),
        capture_output=True,
        check=False,
    )
    if email.returncode != 0:
        identity = [
            "-c",
            "user.name=python-repo",
            "-c",
            "user.email=python-repo@localhost",
        ]
    for command in (
        ["git", "init", "--quiet", "--initial-branch=main"],
        ["git", "add", "--all"],
        ["git", *identity, "commit", "--quiet", "--message", GIT_COMMIT_MESSAGE],
    ):
        error = run_command(command, output)
        if error is not None:
            return error
    return None


def github_create_command(project_name: str, *, private: bool) -> list[str]:
    visibility = "--private" if private else "--public"
    return [
        "gh",
        "repo",
        "create",
        project_name,
        visibility,
        "--source",
        ".",
        "--remote",
        "origin",
        "--push",
    ]


def print_next_steps(project_name: str, output: Path) -> None:
    print(f"Created {project_name} in {output}")
    print("Next:")
    print(f"  cd {output}")
    print("  just bootstrap")


def run_init(project_name: str, package_name: str, output: Path) -> int:
    error = generate(project_name, package_name, output)
    if error is not None:
        print(error)
        return 2
    print_next_steps(project_name, output)
    return 0


def main() -> int:
    """Legacy positional interface, kept for the pack's own tests and validation."""
    if len(sys.argv) != 4:
        print(
            "Usage: python3 instantiate.py <project-name> <package_name> <output-dir>"
        )
        print("   or: python-repo init <project-name> [directory] [--package NAME]")
        return 2
    project_name, package_name, output_arg = sys.argv[1:]
    output = Path(output_arg).expanduser().resolve()
    return run_init(project_name, package_name, output)


def cli(argv: list[str] | None = None) -> int:
    """Entry point of the installed ``python-repo`` console script."""
    parser = argparse.ArgumentParser(
        prog="python-repo",
        description="Create Python repositories from the design-guardrails template.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser(
        "init",
        help="create <directory>/<name> from the template",
        description=(
            "Create a new repository at <directory>/<name>, initialize git with "
            "an initial commit, and create a private GitHub repository with gh. "
            "The import package name is derived from <name> unless --package is "
            "given."
        ),
    )
    init.add_argument("name", help="project (distribution) name, e.g. my-product")
    init.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="parent directory for the new repository (default: current directory)",
    )
    init.add_argument(
        "--package",
        help="import package name (default: derived from the project name)",
    )
    init.add_argument(
        "--public",
        action="store_true",
        help="create the GitHub repository public instead of private",
    )
    init.add_argument(
        "--no-github",
        action="store_true",
        help="initialize git locally but do not create a GitHub repository",
    )
    init.add_argument(
        "--no-git",
        action="store_true",
        help="skip git initialization entirely (implies --no-github)",
    )
    args = parser.parse_args(argv)

    package_name = args.package or derive_package_name(args.name)
    output = Path(args.directory).expanduser().resolve() / args.name
    if args.package is None and PACKAGE_PATTERN.fullmatch(package_name) is None:
        print(
            f"Could not derive a valid package name from '{args.name}' "
            f"(got '{package_name}'); pass one explicitly with --package."
        )
        return 2

    error = generate(args.name, package_name, output)
    if error is not None:
        print(error)
        return 2

    exit_code = 0
    if not args.no_git:
        error = initialize_git_repository(output)
        if error is not None:
            print(f"Git initialization failed: {error}")
            exit_code = 1
        elif not args.no_github:
            github_command = github_create_command(args.name, private=not args.public)
            if shutil.which("gh") is None:
                print("gh was not found on PATH; no GitHub repository was created.")
                print("Create it later from inside the repository:")
                print(f"  {' '.join(github_command)}")
            else:
                error = run_command(github_command, output)
                if error is not None:
                    print(f"GitHub repository creation failed: {error}")
                    print("Fix the cause (e.g. 'gh auth login', name collision),")
                    print("then run from inside the repository:")
                    print(f"  {' '.join(github_command)}")
                    exit_code = 1

    print_next_steps(args.name, output)
    return exit_code


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        raise SystemExit(cli())
    raise SystemExit(main())
