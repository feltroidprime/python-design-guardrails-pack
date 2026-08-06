#!/usr/bin/env python3
"""Run the six `import-linter` contracts over the discovered capabilities.

`pack/configs/importlinter.ini` holds every rule. This shim holds none. It
discovers two values, injects them into the template, and calls `lint-imports`
on the result:

* the import package name, which is the one directory under `src/`.
* the capability list, which is every directory directly under the package that
  does not start with `_` or `.`.

`import-linter` reads the package name from its config file and gives no
command-line flag for it, so the injection keeps the pack-owned template free of
every identity token.

Two measured facts on `import-linter` 2.13 shape the rendering. A declared layer
that does not exist breaks the `layers` contract, and an empty directory counts
as not existing. A wildcard container also matches `cli`, `composition` and
`_foundation`. The shim therefore injects the discovered list, and it drops each
contract that holds `{capability}` when the project has no capability.
"""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from scripts.identity import DiscoveryError, discover_capabilities, discover_package

CONFIG_TEMPLATE = Path("pack/configs/importlinter.ini")
PACKAGE_PLACEHOLDER = "{package}"
CAPABILITY_PLACEHOLDER = "{capability}"
SECTION_PREFIX = "["
COMMENT_PREFIX = ";"
RENDERED_NAME = "importlinter.ini"


def repository_root() -> Path:
    """The repository root, resolved from this script location."""
    return Path(__file__).resolve().parents[2]


def _is_preamble(line: str) -> bool:
    return not line.strip() or line.startswith(COMMENT_PREFIX)


def _sections(template: str) -> list[list[str]]:
    """Split the template at each section header.

    Blank lines and comments that stand before a header belong to that header's
    section, so dropping a section drops the comment that introduces it.
    """
    sections: list[list[str]] = [[]]
    for line in template.splitlines():
        if line.startswith(SECTION_PREFIX):
            carried: list[str] = []
            while sections[-1] and _is_preamble(sections[-1][-1]):
                carried.insert(0, sections[-1].pop())
            sections.append(carried)
        sections[-1].append(line)
    return sections


def _repeats_per_capability(line: str) -> bool:
    return CAPABILITY_PLACEHOLDER in line and not line.startswith(COMMENT_PREFIX)


def _render_section(section: list[str], capabilities: tuple[str, ...]) -> list[str]:
    rendered: list[str] = []
    for line in section:
        if not _repeats_per_capability(line):
            rendered.append(line)
            continue
        rendered.extend(line.replace(CAPABILITY_PLACEHOLDER, name) for name in capabilities)
    return rendered


def render(template: str, package: str, capabilities: tuple[str, ...]) -> str:
    """Inject the package name and the capability list into the template."""
    rendered: list[str] = []
    for section in _sections(template):
        if not capabilities and any(_repeats_per_capability(line) for line in section):
            continue
        rendered.extend(_render_section(section, capabilities))
    return "\n".join(rendered).replace(PACKAGE_PLACEHOLDER, package) + "\n"


def rendered_config(root: Path) -> str:
    """The runnable `import-linter` config for this tree."""
    template = (root / CONFIG_TEMPLATE).read_text(encoding="utf-8")
    package = discover_package(root)
    return render(template, package, discover_capabilities(root, package))


def lint_imports_command() -> str:
    """The `lint-imports` executable that belongs to the running interpreter."""
    beside_interpreter = Path(sys.executable).parent / "lint-imports"
    if beside_interpreter.is_file():
        return str(beside_interpreter)
    found = shutil.which("lint-imports")
    if found is None:
        raise DiscoveryError("'lint-imports' was not found on PATH.")
    return found


def run(root: Path) -> int:
    config = rendered_config(root)
    command = lint_imports_command()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / RENDERED_NAME
        _ = path.write_text(config, encoding="utf-8")
        completed = subprocess.run(
            (command, "--config", str(path)),
            cwd=root,
            check=False,
        )
    return completed.returncode


def main(argv: list[str]) -> int:
    root = repository_root()
    try:
        if argv == ["--print-config"]:
            print(rendered_config(root), end="")
            return 0
        if argv:
            print("Usage: python -m scripts.import_contracts [--print-config]", file=sys.stderr)
            return 2
        return run(root)
    except (DiscoveryError, OSError) as error:
        print(f"Import contracts did not run: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
