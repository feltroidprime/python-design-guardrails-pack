#!/usr/bin/env python3
"""Reject overlapping ownership roots and repository paths with no single owner."""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tomllib
from typing import cast

from scripts.ownership import (
    AmbiguousOwnershipError,
    OwnershipPathError,
    UnclassifiedPathError,
    classify_path,
)
from scripts.ownership_policy import (
    OwnershipPolicy,
    OwnershipPolicyError,
    load_ownership_policy,
)

REPOSITORY_PATHS_COMMAND = (
    "git",
    "ls-files",
    "-z",
    "--cached",
    "--others",
    "--exclude-standard",
)


class OwnershipGuardError(RuntimeError):
    """Raised when repository paths cannot be enumerated."""


@dataclass(frozen=True, slots=True, kw_only=True)
class GuardViolation:
    code: str
    message: str

    def render(self) -> str:
        return f"{self.code} {self.message}"


@dataclass(frozen=True, slots=True, kw_only=True)
class GuardReport:
    paths: tuple[Path, ...]
    violations: tuple[GuardViolation, ...]


def _roots_overlap(left: PurePosixPath, right: PurePosixPath) -> bool:
    return left == right or left in right.parents or right in left.parents


def root_overlap_violations(policy: OwnershipPolicy) -> tuple[GuardViolation, ...]:
    violations: list[GuardViolation] = []
    for index, left_zone in enumerate(policy.zones):
        for right_zone in policy.zones[index + 1 :]:
            for left_root in left_zone.roots:
                for right_root in right_zone.roots:
                    if _roots_overlap(left_root, right_root):
                        violations.append(
                            GuardViolation(
                                code="OWN001",
                                message=(
                                    f"{left_zone.name}:{left_root} overlaps "
                                    f"{right_zone.name}:{right_root}"
                                ),
                            )
                        )
    return tuple(violations)


def repository_paths(root: Path) -> tuple[Path, ...]:
    completed = subprocess.run(  # noqa: S603  # ARCH-EXCEPTION: ADR-0007
        REPOSITORY_PATHS_COMMAND,
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr).strip() or "git ls-files failed"
        raise OwnershipGuardError(detail)
    return tuple(
        sorted(
            Path(os.fsdecode(raw_path)) for raw_path in completed.stdout.split(b"\0") if raw_path
        )
    )


def path_violations(
    paths: tuple[Path, ...],
    policy: OwnershipPolicy,
) -> tuple[GuardViolation, ...]:
    violations: list[GuardViolation] = []
    for path in paths:
        try:
            _ = classify_path(path, policy)
        except UnclassifiedPathError:
            violations.append(
                GuardViolation(
                    code="OWN002",
                    message=f"unclassified repository path: {path.as_posix()}",
                )
            )
        except AmbiguousOwnershipError as error:
            violations.append(
                GuardViolation(
                    code="OWN003",
                    message=str(error),
                )
            )
    return tuple(violations)


def check_repository(root: Path) -> GuardReport:
    policy = load_ownership_policy(root)
    paths = repository_paths(root)
    violations = (*root_overlap_violations(policy), *path_violations(paths, policy))
    return GuardReport(paths=paths, violations=violations)


def _repository_root(argv: list[str]) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the generated repository)",
    )
    values = cast("dict[str, object]", vars(parser.parse_args(argv)))
    root = values["root"]
    if not isinstance(root, Path):
        raise OwnershipGuardError("Repository root must be a path.")
    return root


def main(argv: list[str]) -> int:
    root = _repository_root(argv).resolve()
    try:
        report = check_repository(root)
    except (
        OSError,
        tomllib.TOMLDecodeError,
        OwnershipGuardError,
        OwnershipPathError,
        OwnershipPolicyError,
    ) as error:
        print(f"OWN004 ownership guard could not run: {error}", file=sys.stderr)
        return 1
    if report.violations:
        for violation in report.violations:
            print(violation.render(), file=sys.stderr)
        return 1
    print(f"Ownership guard passed: classified {len(report.paths)} repository paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
