"""Application entry points for declaration-derived index regeneration."""

from dataclasses import dataclass
from hashlib import sha256

from repoctl.modules.repository_generation.application.ports import RepositoryPort
from repoctl.modules.repository_generation.domain.indexes import (
    DerivedCompilation,
    render_derived_indexes,
)
from repoctl.modules.repository_generation.domain.intents import RepositoryPath, RepositorySnapshot
from repoctl.modules.repository_generation.domain.ownership import (
    OwnershipZone,
    RepositoryPathCandidate,
    classify_path,
)
from repoctl.modules.repository_generation.domain.specifications import SYSTEM_CAPABILITY_MODULES


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerationOutcome:
    """The observable result of regenerating all declaration-derived indexes."""

    source_state_sha256: str
    written_targets: tuple[str, ...]


def compile_derived_indexes(snapshot: RepositorySnapshot) -> DerivedCompilation:
    """Compile every derived projection from the snapshot's declarations alone."""
    return render_derived_indexes(
        package=snapshot.package,
        declarations=snapshot.declarations,
        ownership_zones=snapshot.ownership_zones,
        approved_system_modules=SYSTEM_CAPABILITY_MODULES,
    )


def _digest(content: bytes | None) -> str:
    return "absent" if content is None else f"sha256:{sha256(content).hexdigest()}"


def _derived_path(path: RepositoryPath, snapshot: RepositorySnapshot) -> RepositoryPathCandidate:
    candidate = RepositoryPathCandidate(value=path.value)
    if classify_path(candidate, snapshot.ownership_zones) != OwnershipZone("DERIVED"):
        message = f"Derived-index regeneration cannot write outside DERIVED: {path.value}"
        raise ValueError(message)
    return candidate


def _write_changed_indexes(
    compilation: DerivedCompilation,
    snapshot: RepositorySnapshot,
    repository: RepositoryPort,
) -> tuple[str, ...]:
    written: list[str] = []
    for path, text in compilation.writes:
        candidate = _derived_path(path, snapshot)
        content = text.encode("utf-8")
        current = repository.read_bytes(candidate)
        if current == content:
            continue
        repository.write_if_matches(candidate, content, expected_digest=_digest(current))
        written.append(path.value)
    return tuple(written)


def generate(snapshot: RepositorySnapshot, repository: RepositoryPort) -> GenerationOutcome:
    """Regenerate exactly the derived files described by one immutable snapshot."""
    compilation = compile_derived_indexes(snapshot)
    return GenerationOutcome(
        source_state_sha256=compilation.source_state_sha256,
        written_targets=_write_changed_indexes(compilation, snapshot, repository),
    )
