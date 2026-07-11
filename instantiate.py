#!/usr/bin/env python3
"""Instantiate the repository template using only the standard library."""

from pathlib import Path
import re
import shutil
import sys

PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
PROJECT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


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


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: python3 instantiate.py <project-name> <package_name> <output-dir>"
        )
        return 2

    project_name, package_name, output_arg = sys.argv[1:]
    if PROJECT_PATTERN.fullmatch(project_name) is None:
        print(
            "Project name must contain only lowercase letters, digits, '.', '_' or '-'."
        )
        return 2
    if PACKAGE_PATTERN.fullmatch(package_name) is None:
        print("Package name must be a valid lowercase Python identifier.")
        return 2

    source = Path(__file__).resolve().parent / "template"
    output = Path(output_arg).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        print(f"Refusing to overwrite non-empty directory: {output}")
        return 2

    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, output, dirs_exist_ok=True)

    package_placeholder = output / "src" / "__PACKAGE__"
    package_destination = output / "src" / package_name
    package_placeholder.rename(package_destination)

    replacements = {
        "__PROJECT_NAME__": project_name,
        "__PACKAGE__": package_name,
    }
    for path in output.rglob("*"):
        replace_tokens(path, replacements)

    print(f"Created {project_name} in {output}")
    print("Next:")
    print(f"  cd {output}")
    print("  uv sync --all-groups")
    print("  uv run pre-commit install --hook-type pre-commit --hook-type pre-push")
    print("  uv run python scripts/quality_gate.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
