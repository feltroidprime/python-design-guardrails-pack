"""Load the generated repository's single ownership-root declaration."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import tomllib
from typing import cast


class OwnershipPolicyError(ValueError):
    """Raised when the ownership-root declaration is malformed."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ZoneRoots:
    """The repository-relative roots belonging to one ownership zone."""

    name: str
    roots: tuple[PurePosixPath, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnershipPolicy:
    """Ownership roots loaded from the repository's architecture declaration."""

    source: Path
    zones: tuple[ZoneRoots, ...]


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OwnershipPolicyError(f"{name} must be a TOML table")
    return cast("dict[str, object]", value)


def _non_blank_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OwnershipPolicyError(f"{name} must be a non-blank string")
    return value.strip()


def _root_path(value: object, label: str) -> PurePosixPath:
    text = _non_blank_string(value, label)
    root = PurePosixPath(text)
    if root.is_absolute() or ".." in root.parts or root == PurePosixPath("."):
        raise OwnershipPolicyError(f"{label} must be a non-empty repository-relative path")
    return root


def _zone_roots(name: str, value: object) -> ZoneRoots:
    if not isinstance(value, list) or not value:
        raise OwnershipPolicyError(f"ownership.roots.{name} must be a non-empty array")
    items = cast("list[object]", value)
    roots = tuple(_root_path(root, f"ownership.roots.{name}") for root in items)
    if len(set(roots)) != len(roots):
        raise OwnershipPolicyError(f"ownership.roots.{name} repeats a root")
    return ZoneRoots(name=_non_blank_string(name, "ownership zone name"), roots=roots)


def load_ownership_policy(repository_root: Path) -> OwnershipPolicy:
    """Load ownership roots; path classification itself remains filesystem-free."""
    source = repository_root / "architecture.toml"
    raw = _mapping(tomllib.loads(source.read_text(encoding="utf-8")), "architecture.toml")
    ownership = _mapping(raw.get("ownership"), "ownership")
    roots = _mapping(ownership.get("roots"), "ownership.roots")
    zones = tuple(_zone_roots(name, value) for name, value in roots.items())
    if not zones:
        raise OwnershipPolicyError("ownership.roots must declare at least one zone")
    return OwnershipPolicy(source=source, zones=zones)
