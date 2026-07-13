#!/usr/bin/env python3
"""Documentation fitness functions: keep the docs map and its documents true.

Prose drifts silently; this guard turns the documentation rules declared in
``docs/README.md`` into gate failures:

- DOC001: a path referenced by a markdown document does not exist;
- DOC002: an ``ARCH-EXCEPTION`` marker names an ADR that does not exist;
- DOC003-DOC006: ADR file-name, heading, front-matter, and numbering
  conventions;
- DOC007: a markdown document is not registered in the docs map.
"""

from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import TYPE_CHECKING

from scripts.architecture_policy import Policy, load_policy
from scripts.architecture_rules import python_files

if TYPE_CHECKING:
    from collections.abc import Iterator

MAP_RELATIVE = Path("docs") / "README.md"
ADR_RELATIVE = Path("docs") / "adr"
GENERATED_RELATIVE = Path("docs") / "architecture" / "likec4" / "generated"

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
INLINE_CODE = re.compile(r"`([^`\n]+)`")
PATH_CHARSET = re.compile(r"[\w./-]+", re.ASCII)
PATH_SUFFIXES = (".py", ".md", ".c4", ".toml", ".json", ".yml", ".yaml", ".cfg", ".txt")
ADR_FILE_NAME = re.compile(r"(\d{4})-[a-z0-9][a-z0-9-]*\.md")
ADR_FRONT_MATTER_KEYS = ("- Status:", "- Date:", "- Owners:", "- Revisit trigger:")
ADR_STATUSES = frozenset({"proposed", "accepted", "rejected", "superseded", "deprecated"})


@dataclass(frozen=True, slots=True, kw_only=True)
class DocViolation:
    path: Path
    line: int
    code: str
    message: str

    def render(self, root: Path) -> str:
        return f"{self.path.relative_to(root)}:{self.line}: {self.code} {self.message}"


def markdown_files(root: Path) -> list[Path]:
    """Every prose document the guard owns: root-level, docs/, and .github/."""
    generated = root / GENERATED_RELATIVE
    candidates = (
        *root.glob("*.md"),
        *(root / "docs").rglob("*.md"),
        *(root / ".github").rglob("*.md"),
    )
    return sorted(path for path in candidates if generated not in path.parents)


def visible_lines(text: str) -> list[str]:
    """Markdown lines with fenced code blocks blanked, preserving line numbers."""
    lines: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            lines.append("")
            continue
        lines.append("" if fenced else line)
    return lines


def path_like(span: str) -> bool:
    """An inline-code span the guard treats as a path claim, not free text."""
    return (
        "/" in span
        and PATH_CHARSET.fullmatch(span) is not None
        and (span.endswith(PATH_SUFFIXES) or span.endswith("/"))
    )


def line_references(line: str) -> Iterator[str]:
    """Path claims on one markdown line: link targets and path-like code spans."""
    for link in MARKDOWN_LINK.finditer(line):
        target = link.group(1).split("#", 1)[0]
        if target and "://" not in target and not target.startswith("mailto:"):
            yield target
    for span in INLINE_CODE.finditer(line):
        if path_like(span.group(1)):
            yield span.group(1)


def resolution_bases(source: Path, policy: Policy) -> tuple[Path, Path, Path]:
    """Documents cite paths from their own directory, the repo root, or the package."""
    return (source.parent, policy.root, policy.package_root)


def check_references(source: Path, lines: list[str], policy: Policy) -> Iterator[DocViolation]:
    for number, line in enumerate(lines, start=1):
        for reference in line_references(line):
            if any((base / reference).exists() for base in resolution_bases(source, policy)):
                continue
            yield DocViolation(
                path=source,
                line=number,
                code="DOC001",
                message=(
                    f"reference `{reference}` does not exist relative to this file, "
                    f"the repository root, or src/{policy.package}/"
                ),
            )


def adr_front_matter_violations(path: Path, lines: list[str]) -> Iterator[DocViolation]:
    for key in ADR_FRONT_MATTER_KEYS:
        if not any(line.startswith(key) for line in lines):
            yield DocViolation(
                path=path, line=1, code="DOC005", message=f"ADR front matter is missing `{key}`"
            )
    for number, line in enumerate(lines, start=1):
        if (
            line.startswith("- Status:")
            and line.removeprefix("- Status:").strip() not in ADR_STATUSES
        ):
            yield DocViolation(
                path=path,
                line=number,
                code="DOC005",
                message=f"ADR status must be one of {', '.join(sorted(ADR_STATUSES))}",
            )


def check_adr_file(path: Path) -> Iterator[DocViolation]:
    name = ADR_FILE_NAME.fullmatch(path.name)
    if name is None:
        yield DocViolation(
            path=path,
            line=1,
            code="DOC003",
            message="ADR file name must match NNNN-kebab-case.md",
        )
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = f"# ADR-{name.group(1)}:"
    if not lines or not lines[0].startswith(heading):
        yield DocViolation(
            path=path,
            line=1,
            code="DOC004",
            message=f"ADR heading must start with `{heading}` (matching the file name)",
        )
    yield from adr_front_matter_violations(path, lines)


def check_adr_numbering(root: Path) -> Iterator[DocViolation]:
    """ADR numbers are contiguous from 0000: supersede records, never delete them."""
    adr_dir = root / ADR_RELATIVE
    numbered: dict[int, list[Path]] = {}
    for path in sorted(adr_dir.glob("*.md")):
        name = ADR_FILE_NAME.fullmatch(path.name)
        if name is not None:
            numbered.setdefault(int(name.group(1)), []).append(path)
    for number, paths in sorted(numbered.items()):
        for duplicate in paths[1:]:
            yield DocViolation(
                path=duplicate,
                line=1,
                code="DOC006",
                message=f"duplicate ADR number {number:04d} ({paths[0].name} already uses it)",
            )
    for expected, number in enumerate(sorted(numbered)):
        if number != expected:
            yield DocViolation(
                path=adr_dir,
                line=1,
                code="DOC006",
                message=f"ADR numbers must be contiguous from 0000; missing ADR-{expected:04d}",
            )
            return


def check_exception_markers(policy: Policy, adr_numbers: frozenset[int]) -> Iterator[DocViolation]:
    """Every concrete `ARCH-EXCEPTION: ADR-NNNN` marker must point at a real ADR."""
    marker = re.compile(re.escape(policy.exception_marker) + r"(\d{4})")
    for path in (*python_files(policy), *markdown_files(policy.root)):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in marker.finditer(line):
                if int(match.group(1)) not in adr_numbers:
                    yield DocViolation(
                        path=path,
                        line=number,
                        code="DOC002",
                        message=f"marker references ADR-{match.group(1)}, absent from docs/adr/",
                    )


def map_targets(map_path: Path, policy: Policy) -> frozenset[Path]:
    """Files and directories the docs map registers, resolved to real paths."""
    targets: set[Path] = set()
    for line in visible_lines(map_path.read_text(encoding="utf-8")):
        for reference in line_references(line):
            for base in resolution_bases(map_path, policy):
                candidate = (base / reference).resolve()
                if candidate.exists():
                    targets.add(candidate)
    return frozenset(targets)


def check_registration(
    documents: list[Path], map_path: Path, policy: Policy
) -> Iterator[DocViolation]:
    """Rule 3 of the map: every document claims a row (directly or via its directory)."""
    if not map_path.is_file():
        yield DocViolation(
            path=policy.root,
            line=1,
            code="DOC007",
            message=f"the documentation map {MAP_RELATIVE} does not exist",
        )
        return
    targets = map_targets(map_path, policy)
    for document in documents:
        if document == map_path:
            continue
        resolved = document.resolve()
        if resolved in targets or any(parent in targets for parent in resolved.parents):
            continue
        yield DocViolation(
            path=document,
            line=1,
            code="DOC007",
            message=f"document is not registered in {MAP_RELATIVE}",
        )


def check_documentation(policy: Policy) -> list[DocViolation]:
    root = policy.root
    documents = markdown_files(root)
    adr_numbers = frozenset(
        int(name.group(1))
        for path in (root / ADR_RELATIVE).glob("*.md")
        if (name := ADR_FILE_NAME.fullmatch(path.name)) is not None
    )
    violations: list[DocViolation] = []
    for document in documents:
        lines = visible_lines(document.read_text(encoding="utf-8"))
        violations.extend(check_references(document, lines, policy))
        if document.parent == root / ADR_RELATIVE:
            violations.extend(check_adr_file(document))
    violations.extend(check_adr_numbering(root))
    violations.extend(check_exception_markers(policy, adr_numbers))
    violations.extend(check_registration(documents, root / MAP_RELATIVE, policy))
    return violations


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations = check_documentation(load_policy(root))
    if violations:
        for item in violations:
            print(item.render(root))
        print(f"\n{len(violations)} documentation violation(s).", file=sys.stderr)
        return 1
    print("Documentation guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
