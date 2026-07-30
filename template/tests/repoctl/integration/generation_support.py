"""Shared declaration and output helpers for derived-index integration evidence."""

from repoctl.modules.repository_generation.api import (
    GenerationOutcome,
    RepositoryPathCandidate,
    RepositoryPort,
    generate,
)

GENERATED_TARGETS = (
    "src/acme/_generated/active_capabilities.py",
    "src/acme/_generated/composition.py",
    "src/acme/_generated/cli_catalog.py",
    "proof/_generated/index.json",
)


def write_declaration(
    repository: RepositoryPort,
    *,
    name: str,
    status: str,
    schema_version: int = 1,
    python_module: str | None = None,
    proof_catalog: str | None = None,
    factory: str | None = None,
    cli_catalog: str | None = None,
) -> None:
    """Write one raw capability declaration through the normal adapter boundary."""
    module = python_module or f"acme.modules.{name}"
    rendered_proof_catalog = proof_catalog or f"proof/modules/{name}.toml"
    rendered_factory = factory if factory is not None else f"{module}.bootstrap:build"
    rendered_cli_catalog = (
        cli_catalog
        if cli_catalog is not None
        else f"{module}.adapters.inbound.cli_catalog:COMMANDS"
    )
    content = f'''schema_version = {schema_version}
name = "{name}"
python_module = "{module}"
status = "{status}"
proof_catalog = "{rendered_proof_catalog}"

[boundaries]
inbound = ["python"]
outbound = []

[activation]
api = "{module}.api"
factory = "{rendered_factory}"
cli_catalog = "{rendered_cli_catalog}"
'''
    repository.write_if_matches(
        RepositoryPathCandidate(value=f".repo/capabilities/{name}.toml"),
        content.encode("utf-8"),
        expected_digest="absent",
    )


def generate_indexes(repository: RepositoryPort) -> GenerationOutcome:
    """Compile and replace the declaration-derived output set for its current snapshot."""
    return generate(repository.snapshot(), repository)


def generated_bytes(repository: RepositoryPort) -> dict[str, bytes | None]:
    """Return the current bytes of every derived index target."""
    return {
        target: repository.read_bytes(RepositoryPathCandidate(value=target))
        for target in GENERATED_TARGETS
    }
