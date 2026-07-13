#!/usr/bin/env python3
"""Instantiate the repository template using only the standard library.

Two entry points share the same generator core:

- legacy positional form: ``python3 instantiate.py <project> <package> <output-dir>``;
- installed CLI (``python-repo`` console script): ``python-repo init <name> [directory] [--package NAME]``.
"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
PROJECT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

PROJECT_TOKEN = "__PROJECT_NAME__"
PACKAGE_TOKEN = "__PACKAGE__"
PLACEHOLDER_TOKENS = (PROJECT_TOKEN, PACKAGE_TOKEN)

# Local artifacts that must never reach a generated repository, even if a
# maintainer accidentally leaves them inside template/.
IGNORED_ARTIFACT_PATTERNS = (
    ".DS_Store",
    ".basedpyright",
    ".coverage",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "*.egg-info",
    "*.py[cod]",
    "__pycache__",
    "coverage.xml",
    "dist",
    "htmlcov",
    "uv.lock",
)


def replace_tokens(path: Path, replacements: dict[str, str]) -> None:
    if not path.is_file():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for token, value in replacements.items():
        content = content.replace(token, value)
    path.write_text(content, encoding="utf-8")


def derive_package_name(project_name: str) -> str:
    """Best-effort import package derived from the project name."""
    return project_name.replace("-", "_").replace(".", "_")


def validate_names(project_name: str, package_name: str) -> str | None:
    """Return an error message, or None when both names are acceptable."""
    if PROJECT_PATTERN.fullmatch(project_name) is None:
        return "Project name must contain only lowercase letters, digits, '.', '_' or '-'."
    if PACKAGE_PATTERN.fullmatch(package_name) is None:
        return "Package name must be a valid lowercase Python identifier."
    return None


def generate(project_name: str, package_name: str, output: Path) -> str | None:
    """Copy the template into *output*. Return an error message, or None on success."""
    source = Path(__file__).resolve().parent / "template"
    if output.exists() and any(output.iterdir()):
        return f"Refusing to overwrite non-empty directory: {output}"

    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        output,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*IGNORED_ARTIFACT_PATTERNS),
    )

    package_placeholder = output / "src" / PACKAGE_TOKEN
    package_destination = output / "src" / package_name
    package_placeholder.rename(package_destination)

    replacements = {
        PROJECT_TOKEN: project_name,
        PACKAGE_TOKEN: package_name,
    }
    for path in output.rglob("*"):
        replace_tokens(path, replacements)
    return None


GIT_COMMIT_MESSAGE = "Initial commit from python-design-guardrails-pack"


def run_command(command: list[str], cwd: Path) -> str | None:
    """Run a command in *cwd*; return an error message on failure, None on success."""
    completed = subprocess.run(command, cwd=cwd, check=False)
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
    print("  uv sync --all-groups")
    print("  uv run pre-commit install --hook-type pre-commit --hook-type pre-push")
    print("  uv run python scripts/quality_gate.py")


def run_init(project_name: str, package_name: str, output: Path) -> int:
    error = validate_names(project_name, package_name) or generate(
        project_name, package_name, output
    )
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

    error = validate_names(args.name, package_name) or generate(
        args.name, package_name, output
    )
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
