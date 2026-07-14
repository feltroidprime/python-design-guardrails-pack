#!/usr/bin/env python3
"""End-to-end validation of the Copier template pack.

The loop:

1. verify template/ contains no local runtime artifacts;
2. instantiate a throwaway repository inside a temporary directory;
3. verify no unrendered Jinja survives in file names or contents;
4. resolve the generated repository's pinned dependencies with uv;
5. run the generated repository's own full quality gate;
6. delete the throwaway repository.

Every failure message states what broke and how to fix it, so both humans
and coding agents can act on it without re-deriving the intent.
"""

import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "template"
COPIER_CONFIG = REPO_ROOT / "copier.yml"
PROJECT_NAME = "orchard-billing"
PACKAGE_NAME = "orchard_billing"


def artifact_exclusion_patterns() -> tuple[str, ...]:
    """Read artifact exclusions from copier.yml, their single source of truth."""
    patterns: list[str] = []
    in_exclude = False
    for raw_line in COPIER_CONFIG.read_text(encoding="utf-8").splitlines():
        if raw_line == "_exclude:":
            in_exclude = True
            continue
        if in_exclude and raw_line.startswith("  - "):
            patterns.append(raw_line.removeprefix("  - ").strip('"\''))
            continue
        if in_exclude and raw_line and not raw_line.startswith(" "):
            break
    if not patterns:
        raise ValueError("copier.yml must define a non-empty _exclude list")
    return tuple(patterns)


def find_forbidden_artifacts(root: Path) -> list[Path]:
    """Return every entry under *root* matching an ignored artifact pattern."""
    patterns = artifact_exclusion_patterns()
    return sorted(
        path
        for path in root.rglob("*")
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
    )


def find_unrendered_jinja(root: Path) -> list[str]:
    """Return human-readable locations where template syntax survives rendering."""
    occurrences: list[str] = []
    jinja_syntax = re.compile(
        r"(?<![$\{])\{\{[-+]?\s*[A-Za-z_]|\{%[-+]?\s*[A-Za-z_]|\{#[-+]?"
    )
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.name.endswith(".jinja"):
            occurrences.append(f"{relative}: stray .jinja template suffix")
        if jinja_syntax.search(relative.as_posix()):
            occurrences.append(f"{relative}: Jinja syntax in file or directory name")
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if jinja_syntax.search(line):
                occurrences.append(f"{relative}:{line_number}: contains Jinja syntax")
    return occurrences


def fail(step: str, details: list[str], fix: str) -> int:
    print(f"\nVALIDATION FAILED at step: {step}", file=sys.stderr)
    for detail in details:
        print(f"  {detail}", file=sys.stderr)
    print(f"FIX: {fix}", file=sys.stderr)
    return 1


def run_step(name: str, command: list[str], cwd: Path) -> int:
    print(f"\n=== {name} ===", flush=True)
    print(f"$ {' '.join(command)}  (cwd={cwd})", flush=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"}
    }
    completed = subprocess.run(command, cwd=cwd, env=environment, check=False)
    return completed.returncode


def main() -> int:
    print("=== template cleanliness ===")
    artifacts = find_forbidden_artifacts(TEMPLATE_ROOT)
    if artifacts:
        return fail(
            "template cleanliness",
            [str(path.relative_to(REPO_ROOT)) for path in artifacts],
            "Delete these local artifacts from template/. The forbidden patterns are "
            "the _exclude entries in copier.yml.",
        )
    print("template/ contains no local runtime artifacts.")

    if shutil.which("uv") is None:
        return fail(
            "toolchain",
            ["'uv' was not found on PATH."],
            "Install uv (https://docs.astral.sh/uv/) before running pack validation.",
        )

    with tempfile.TemporaryDirectory(prefix="guardrails-pack-validate-") as scratch:
        target = Path(scratch) / PROJECT_NAME

        exit_code = run_step(
            "instantiate throwaway repository",
            [sys.executable, str(REPO_ROOT / "instantiate.py"), PROJECT_NAME, PACKAGE_NAME, str(target)],
            REPO_ROOT,
        )
        if exit_code != 0:
            return fail(
                "instantiate",
                [f"instantiate.py exited with {exit_code}."],
                "Read the generator output above; fix instantiate.py or template/.",
            )

        print("\n=== unrendered Jinja scan ===")
        leftovers = find_unrendered_jinja(target)
        if leftovers:
            return fail(
                "unrendered Jinja scan",
                leftovers,
                "Every rendered template file and path must use the .jinja suffix; check "
                "copier.yml and the canonical source under template/.",
            )
        print("No unrendered Jinja survives in the generated repository.")

        exit_code = run_step("resolve dependencies", ["uv", "sync", "--all-groups"], target)
        if exit_code != 0:
            return fail(
                "dependency resolution",
                [f"'uv sync --all-groups' exited with {exit_code}."],
                "Check template/pyproject.toml.jinja pins and network access; the generated "
                "repository must resolve with the pinned uv version.",
            )

        exit_code = run_step(
            "downstream quality gate",
            ["uv", "run", "python", "scripts/quality_gate.py"],
            target,
        )
        if exit_code != 0:
            return fail(
                "downstream quality gate",
                [f"quality_gate.py exited with {exit_code}."],
                "The generated repository fails its own gate. Fix the canonical source "
                "under template/ (never a generated copy) and re-run 'just validate'.",
            )

    print("\nPack validation passed: template is clean, instantiation is fully rendered,")
    print("and the generated repository passes its full quality gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
