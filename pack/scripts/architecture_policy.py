"""Load and validate the deterministic architecture policy (architecture.toml).

Two roots exist and they are not the same. The repository root holds `src/`,
`tests/` and `docs/`. The pack root is `pack/` below it, and it holds the
policy, the guard scripts, the proof surface and the pack's own tests.

The policy declares no package name. Identity lives in `pyproject.toml`, so the
package is derived: `src/` holds exactly one directory, and that directory is
the package. A pack-owned file that named the package could not be
byte-identical in every project (invariant O1 of #85).
"""

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import cast

PACK_DIRECTORY = "pack"
POLICY_RELATIVE = Path(PACK_DIRECTORY) / "architecture.toml"
SOURCE_DIRECTORY = "src"
TEST_DIRECTORY = "tests"
VERIFICATION_DIRECTORY = "verification"
SCRIPTS_DIRECTORY = "scripts"


class PolicyError(ValueError):
    """Raised when the tree cannot supply a deterministic architecture policy."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    root: Path
    pack_root: Path
    source_root: Path
    package: str
    package_root: Path
    domain_root: Path
    test_roots: tuple[Path, ...]
    max_module_lines: int
    max_test_module_lines: int
    max_function_lines: int
    max_class_lines: int
    forbidden_module_stems: frozenset[str]
    exception_marker: str
    immutable_module_stems: frozenset[str]
    forbidden_import_roots: frozenset[str]
    forbidden_call_suffixes: frozenset[str]


def mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a TOML table")
    return cast("dict[str, object]", value)


def string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def integer(value: object, name: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def string_set(value: object, name: str) -> frozenset[str]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be an array of strings")
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise TypeError(f"{name} must be an array of strings")
    return frozenset(cast("list[str]", items))


def derive_package(source_root: Path) -> str:
    """Name the package from the tree: `src/` holds exactly one directory."""
    candidates = sorted(
        path.name
        for path in source_root.iterdir()
        if path.is_dir() and not path.name.startswith((".", "__")) and path.suffix != ".egg-info"
    )
    if len(candidates) != 1:
        found = ", ".join(candidates) or "nothing"
        raise PolicyError(
            f"{source_root.as_posix()} must hold exactly one package directory; found {found}"
        )
    return candidates[0]


def load_policy(root: Path) -> Policy:
    """Load the policy of one repository root, from `pack/architecture.toml`."""
    pack_root = root / PACK_DIRECTORY
    raw = mapping(tomllib.loads((root / POLICY_RELATIVE).read_text()), "root")
    project = mapping(raw["project"], "project")
    limits = mapping(raw["limits"], "limits")
    conventions = mapping(raw["conventions"], "conventions")
    domain = mapping(raw["domain"], "domain")
    source_root = root / string(project["source_root"], "project.source_root")
    package = derive_package(source_root)
    package_root = source_root / package
    domain_root = package_root / string(domain["package"], "domain.package")
    return Policy(
        root=root,
        pack_root=pack_root,
        source_root=source_root,
        package=package,
        package_root=package_root,
        domain_root=domain_root,
        test_roots=(
            root / TEST_DIRECTORY,
            pack_root / TEST_DIRECTORY,
            pack_root / VERIFICATION_DIRECTORY,
        ),
        max_module_lines=integer(limits["max_module_lines"], "limits.max_module_lines"),
        max_test_module_lines=integer(
            limits["max_test_module_lines"], "limits.max_test_module_lines"
        ),
        max_function_lines=integer(limits["max_function_lines"], "limits.max_function_lines"),
        max_class_lines=integer(limits["max_class_lines"], "limits.max_class_lines"),
        forbidden_module_stems=string_set(
            conventions["forbidden_module_stems"], "conventions.forbidden_module_stems"
        ),
        exception_marker=string(conventions["exception_marker"], "conventions.exception_marker"),
        immutable_module_stems=string_set(
            domain["immutable_module_stems"], "domain.immutable_module_stems"
        ),
        forbidden_import_roots=string_set(
            domain["forbidden_import_roots"], "domain.forbidden_import_roots"
        ),
        forbidden_call_suffixes=string_set(
            domain["forbidden_call_suffixes"], "domain.forbidden_call_suffixes"
        ),
    )
