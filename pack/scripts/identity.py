"""Discover the two layout facts that every pack-owned script needs.

The pack-owned surface carries no identity token, so a script reads the import
package name from the filesystem instead of a configuration file. A capability
is one directory directly under that package, so the capability list is a
`listdir` as well.

Both answers come from directory names only. A capability whose layers are
absent or empty is still a capability, because the gate must be able to report
that violation rather than hide it.
"""

from pathlib import Path

__all__ = ["DiscoveryError", "discover_capabilities", "discover_package"]

SOURCE_DIRECTORY = "src"
PRIVATE_PREFIXES = (".", "_")


class DiscoveryError(RuntimeError):
    """Raised when the tree does not carry exactly one import package."""


def _visible_names(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            path.name
            for path in root.iterdir()
            if path.is_dir() and not path.name.startswith(PRIVATE_PREFIXES)
        )
    )


def discover_package(root: Path) -> str:
    """The one import package of the tree, read from `src/`."""
    source_root = root / SOURCE_DIRECTORY
    if not source_root.is_dir():
        raise DiscoveryError(f"{SOURCE_DIRECTORY}/ does not exist.")
    candidates = _visible_names(source_root)
    if len(candidates) != 1:
        raise DiscoveryError(
            f"{SOURCE_DIRECTORY}/ must hold exactly one package; found {list(candidates)}."
        )
    return candidates[0]


def discover_capabilities(root: Path, package: str) -> tuple[str, ...]:
    """Every capability directory directly under the package."""
    package_root = root / SOURCE_DIRECTORY / package
    if not package_root.is_dir():
        return ()
    return _visible_names(package_root)
