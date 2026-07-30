"""Immutable declared state and structural capability intent."""

from dataclasses import dataclass, fields
import json
from typing import Literal, cast, override

import icontract

from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipRoot,
    OwnershipZoneRoots,
)
from repoctl.modules.repository_generation.domain.specifications import (
    capability_name_is_valid,
    declaration_names_are_unique,
    digest_is_valid,
    file_paths_are_unique,
    lifecycle_status_is_valid,
    ownership_zone_names_are_complete,
    plan_path_is_repository_relative,
    schema_version_is_supported,
    strings_are_canonical,
)

type CapabilityStatus = Literal["draft", "active", "retired"]


def _canonical_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _intent_schema_holds(self: object) -> bool:
    return schema_version_is_supported(cast("CapabilityIntent", self).schema_version)


def _intent_name_holds(self: object) -> bool:
    return capability_name_is_valid(cast("CapabilityIntent", self).name)


def _intent_boundaries_hold(self: object) -> bool:
    intent = cast("CapabilityIntent", self)
    return strings_are_canonical(intent.inbound) and strings_are_canonical(intent.outbound)


@icontract.invariant(
    _intent_schema_holds,
    description="INTENT-SCHEMA-SUPPORTED: intent schema version must be supported",
)
@icontract.invariant(
    _intent_name_holds,
    description="INTENT-NAME-CANONICAL: capability name must be lowercase snake case",
)
@icontract.invariant(
    _intent_boundaries_hold,
    description="INTENT-BOUNDARIES-CANONICAL: boundary identifiers must be sorted and unique",
)
@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityIntent:
    """Structural user intent without guessed product semantics."""

    schema_version: int
    name: str
    inbound: tuple[str, ...]
    outbound: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inbound", _canonical_strings(self.inbound))
        object.__setattr__(self, "outbound", _canonical_strings(self.outbound))

    @override
    def __getstate__(self) -> list[object]:
        """Keep slotted invariant-bearing values copyable for symbolic execution."""
        return [getattr(self, field.name, None) for field in fields(self)]

    def __setstate__(self, state: list[object]) -> None:
        """Restore a copied value through the frozen dataclass boundary."""
        for field, value in zip(fields(self), state, strict=True):
            object.__setattr__(self, field.name, value)


def _declaration_name_holds(self: object) -> bool:
    return capability_name_is_valid(cast("CapabilityDeclaration", self).name)


def _declaration_status_holds(self: object) -> bool:
    return lifecycle_status_is_valid(cast("CapabilityDeclaration", self).status)


def _declaration_boundaries_hold(self: object) -> bool:
    declaration = cast("CapabilityDeclaration", self)
    return strings_are_canonical(declaration.inbound) and strings_are_canonical(
        declaration.outbound
    )


@icontract.invariant(
    _declaration_name_holds,
    description="DECLARATION-NAME-CANONICAL: declaration name must be lowercase snake case",
)
@icontract.invariant(
    _declaration_status_holds,
    description="DECLARATION-STATUS-KNOWN: declaration status must be draft, active, or retired",
)
@icontract.invariant(
    _declaration_boundaries_hold,
    description="DECLARATION-BOUNDARIES-CANONICAL: boundaries must be sorted and unique",
)
@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityDeclaration:
    """One versioned capability declaration captured in a snapshot."""

    name: str
    python_module: str
    status: Literal["draft", "active", "retired"]
    proof_catalog: str
    inbound: tuple[str, ...]
    outbound: tuple[str, ...]
    api: str
    factory: str
    cli_catalog: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "inbound", _canonical_strings(self.inbound))
        object.__setattr__(self, "outbound", _canonical_strings(self.outbound))

    def canonical_payload(self) -> dict[str, object]:
        """Return the stable structured representation used by state digests."""
        return {
            "name": self.name,
            "python_module": self.python_module,
            "status": self.status,
            "proof_catalog": self.proof_catalog,
            "inbound": list(self.inbound),
            "outbound": list(self.outbound),
            "api": self.api,
            "factory": self.factory,
            "cli_catalog": self.cli_catalog,
        }

    def canonical_document(self) -> str:
        """Render the stable declaration document used for writes and source digests."""
        return "\n".join(
            (
                "schema_version = 1",
                f"name = {_toml_string(self.name)}",
                f"python_module = {_toml_string(self.python_module)}",
                f"status = {_toml_string(self.status)}",
                f"proof_catalog = {_toml_string(self.proof_catalog)}",
                "",
                "[boundaries]",
                f"inbound = {_toml_array(self.inbound)}",
                f"outbound = {_toml_array(self.outbound)}",
                "",
                "[activation]",
                f"api = {_toml_string(self.api)}",
                f"factory = {_toml_string(self.factory)}",
                f"cli_catalog = {_toml_string(self.cli_catalog)}",
                "",
            )
        )

    @override
    def __getstate__(self) -> list[object]:
        """Keep slotted invariant-bearing values copyable for symbolic execution."""
        return [getattr(self, field.name, None) for field in fields(self)]

    def __setstate__(self, state: list[object]) -> None:
        """Restore a copied value through the frozen dataclass boundary."""
        for field, value in zip(fields(self), state, strict=True):
            object.__setattr__(self, field.name, value)


def _repository_path_holds(self: object) -> bool:
    return plan_path_is_repository_relative(cast("RepositoryPath", self).value)


@icontract.invariant(
    _repository_path_holds,
    description="PLAN-PATH-REPOSITORY-RELATIVE: paths must not escape the repository",
)
@dataclass(frozen=True, slots=True, kw_only=True)
class RepositoryPath:
    """A repository-relative plan or snapshot path before ownership classification."""

    value: str

    @override
    def __getstate__(self) -> list[object]:
        """Keep slotted invariant-bearing values copyable for symbolic execution."""
        return [getattr(self, field.name, None) for field in fields(self)]

    def __setstate__(self, state: list[object]) -> None:
        """Restore a copied value through the frozen dataclass boundary."""
        for field, value in zip(fields(self), state, strict=True):
            object.__setattr__(self, field.name, value)


def _repository_file_path_holds(self: object) -> bool:
    return plan_path_is_repository_relative(cast("RepositoryFile", self).path.value)


def _repository_file_digest_holds(self: object) -> bool:
    return digest_is_valid(cast("RepositoryFile", self).digest)


@icontract.invariant(
    _repository_file_path_holds,
    description="SNAPSHOT-PATH-REPOSITORY-RELATIVE: snapshot paths must not escape the repository",
)
@icontract.invariant(
    _repository_file_digest_holds,
    description="SNAPSHOT-DIGEST-VALID: file state requires a SHA-256 digest",
)
@dataclass(frozen=True, slots=True, kw_only=True)
class RepositoryFile:
    """The content identity of one repository-relative path."""

    path: RepositoryPath
    digest: str

    @override
    def __getstate__(self) -> list[object]:
        """Keep slotted invariant-bearing values copyable for symbolic execution."""
        return [getattr(self, field.name, None) for field in fields(self)]

    def __setstate__(self, state: list[object]) -> None:
        """Restore a copied value through the frozen dataclass boundary."""
        for field, value in zip(fields(self), state, strict=True):
            object.__setattr__(self, field.name, value)


def _snapshot_schema_holds(self: object) -> bool:
    return schema_version_is_supported(cast("RepositorySnapshot", self).schema_version)


def _snapshot_package_holds(self: object) -> bool:
    return capability_name_is_valid(cast("RepositorySnapshot", self).package)


def _snapshot_declarations_hold(self: object) -> bool:
    snapshot = cast("RepositorySnapshot", self)
    return declaration_names_are_unique(
        tuple(declaration.name for declaration in snapshot.declarations)
    )


def _snapshot_files_hold(self: object) -> bool:
    snapshot = cast("RepositorySnapshot", self)
    return file_paths_are_unique(tuple(file.path.value for file in snapshot.files))


def _snapshot_ownership_holds(self: object) -> bool:
    snapshot = cast("RepositorySnapshot", self)
    return ownership_zone_names_are_complete(
        tuple(str(zone.name) for zone in snapshot.ownership_zones)
    ) and all(zone.roots for zone in snapshot.ownership_zones)


@icontract.invariant(
    _snapshot_schema_holds,
    description="SNAPSHOT-SCHEMA-SUPPORTED: snapshot schema version must be supported",
)
@icontract.invariant(
    _snapshot_package_holds,
    description="SNAPSHOT-PACKAGE-CANONICAL: package must be lowercase snake case",
)
@icontract.invariant(
    _snapshot_declarations_hold,
    description="SNAPSHOT-DECLARATIONS-UNIQUE: capability names must not repeat",
)
@icontract.invariant(
    _snapshot_files_hold,
    description="SNAPSHOT-FILES-UNIQUE: file paths must not repeat",
)
@icontract.invariant(
    _snapshot_ownership_holds,
    description="SNAPSHOT-OWNERSHIP-COMPLETE: all four ownership zones require roots",
)
@dataclass(frozen=True, slots=True, kw_only=True)
class RepositorySnapshot:
    """Canonical declared and file state supplied explicitly to pure planning."""

    schema_version: int
    package: str
    declarations: tuple[CapabilityDeclaration, ...]
    files: tuple[RepositoryFile, ...]
    ownership_zones: tuple[OwnershipZoneRoots, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "declarations",
            tuple(sorted(self.declarations, key=lambda declaration: declaration.name)),
        )
        object.__setattr__(
            self,
            "files",
            tuple(sorted(self.files, key=lambda file: file.path.value)),
        )
        object.__setattr__(
            self,
            "ownership_zones",
            tuple(
                OwnershipZoneRoots(
                    name=zone.name,
                    roots=tuple(
                        OwnershipRoot(value=value)
                        for value in sorted({root.value for root in zone.roots})
                    ),
                )
                for zone in sorted(
                    self.ownership_zones,
                    key=lambda candidate: str(candidate.name),
                )
            ),
        )

    @override
    def __getstate__(self) -> list[object]:
        """Keep slotted invariant-bearing values copyable for symbolic execution."""
        return [getattr(self, field.name, None) for field in fields(self)]

    def __setstate__(self, state: list[object]) -> None:
        """Restore a copied value through the frozen dataclass boundary."""
        for field, value in zip(fields(self), state, strict=True):
            object.__setattr__(self, field.name, value)
