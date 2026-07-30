"""Shared capability-declaration decoding for repository filesystem adapters."""

import tomllib
from typing import cast

from repoctl.modules.repository_generation.application.ports import RepositoryPortError
from repoctl.modules.repository_generation.domain.intents import (
    CapabilityDeclaration,
    CapabilityStatus,
)
from repoctl.modules.repository_generation.domain.specifications import (
    lifecycle_status_is_valid,
    schema_version_is_supported,
)


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RepositoryPortError(f"{label} must be a TOML table")
    return cast("dict[str, object]", value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise RepositoryPortError(f"{label} must be a string")
    return value


def _texts(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RepositoryPortError(f"{label} must be an array of strings")
    texts: list[str] = []
    for item in cast("list[object]", value):
        if not isinstance(item, str):
            raise RepositoryPortError(f"{label} must be an array of strings")
        texts.append(item)
    return tuple(texts)


def _status(value: object, label: str) -> CapabilityStatus:
    status = _text(value, label)
    if not lifecycle_status_is_valid(status):
        raise RepositoryPortError(f"{label} is not a known capability state: {status}")
    return cast("CapabilityStatus", status)


def _validate_schema_version(value: object, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not schema_version_is_supported(value)
    ):
        raise RepositoryPortError(f"{label} is not a supported capability declaration schema")


def decode_capability_declaration(content: bytes, location: str) -> CapabilityDeclaration:
    """Parse one supported declaration document without silently down-converting it."""
    try:
        raw: object = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise RepositoryPortError(f"Cannot read capability declaration {location}") from error
    values = _mapping(raw, location)
    _validate_schema_version(values.get("schema_version"), f"{location}.schema_version")
    boundaries = _mapping(values.get("boundaries"), f"{location}.boundaries")
    activation = _mapping(values.get("activation"), f"{location}.activation")
    return CapabilityDeclaration(
        name=_text(values.get("name"), f"{location}.name"),
        python_module=_text(values.get("python_module"), f"{location}.python_module"),
        status=_status(values.get("status"), f"{location}.status"),
        proof_catalog=_text(values.get("proof_catalog"), f"{location}.proof_catalog"),
        inbound=_texts(boundaries.get("inbound"), f"{location}.boundaries.inbound"),
        outbound=_texts(boundaries.get("outbound"), f"{location}.boundaries.outbound"),
        api=_text(activation.get("api"), f"{location}.activation.api"),
        factory=_text(activation.get("factory"), f"{location}.activation.factory"),
        cli_catalog=_text(activation.get("cli_catalog"), f"{location}.activation.cli_catalog"),
    )
