"""Every toolchain pin that exists in more than one place must agree.

This test is the single mechanism behind the "keep version pins coherent"
rule: it discovers occurrences by scanning every tracked file, so no document
needs to enumerate the locations and no location list can go stale. Moving a
pin means updating every copy until this test passes.
"""

from pathlib import Path
import re
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_RECORDS = ("CHANGELOG.md", "VALIDATION.md")
VERSION = r"([0-9][0-9A-Za-z.]*)"
COMMIT = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")


def tracked_files() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        REPO_ROOT / line
        for line in listed.stdout.splitlines()
        if line not in HISTORICAL_RECORDS and (REPO_ROOT / line).is_file()
    ]


def texts() -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        result.append((path.relative_to(REPO_ROOT).as_posix(), text))
    return result


def occurrences(*patterns: str) -> list[tuple[str, str]]:
    compiled = [re.compile(pattern) for pattern in patterns]
    return [
        (relative, match.group(1))
        for relative, text in texts()
        for regex in compiled
        for match in regex.finditer(text)
    ]


def assert_coherent(found: list[tuple[str, str]], minimum: int) -> None:
    assert len(found) >= minimum, found
    assert len({value for _, value in found}) == 1, found


def test_icontract_floor_is_coherent() -> None:
    assert_coherent(occurrences(rf"icontract>={VERSION}"), 3)


def test_prek_floor_is_coherent() -> None:
    assert_coherent(
        occurrences(rf"minimum_prek_version = \"{VERSION}\"", rf"prek>={VERSION}"),
        3,
    )


def test_ruff_floor_is_coherent() -> None:
    assert_coherent(occurrences(rf"ruff>={VERSION}"), 2)


def test_uv_pin_is_coherent() -> None:
    assert_coherent(
        occurrences(
            rf"uv_build=={VERSION}",
            rf"required-version = \">={VERSION},",
            rf"setup-uv@v\d+(?:\.\d+)*\s+with:\s+version: \"{VERSION}\"",
            rf"uv-pre-commit\"\s*rev = \"{VERSION}\"",
        ),
        5,
    )


def test_session_profiler_commit_is_coherent() -> None:
    marker = "session-profiler" + "-optimizer"
    found = [
        (relative, match.group(0))
        for relative, text in texts()
        if marker in text
        for match in COMMIT.finditer(text)
    ]
    assert_coherent(found, 3)
