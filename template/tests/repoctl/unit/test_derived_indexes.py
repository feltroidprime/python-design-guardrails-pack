"""Pure compiler evidence for declaration-derived indexes."""

from typing import Literal

import pytest

from repoctl.modules.repository_generation.api import (
    SYSTEM_CAPABILITY_MODULES,
    CapabilityDeclaration,
    DerivedIndexRenderingError,
    default_ownership_zones,
    render_derived_indexes,
)


def _declaration(
    *,
    name: str,
    python_module: str,
    status: Literal["draft", "active", "retired"],
    inbound: tuple[str, ...] = ("python",),
    factory: str = "",
) -> CapabilityDeclaration:
    return CapabilityDeclaration(
        name=name,
        python_module=python_module,
        status=status,
        proof_catalog=f"proof/modules/{name}.toml",
        inbound=inbound,
        outbound=(),
        api=f"{python_module}.api",
        factory=factory,
        cli_catalog="",
    )


def test_declaration_source_digest_preserves_the_empty_repository_baseline() -> None:
    compilation = render_derived_indexes(
        package="acme",
        declarations=(
            CapabilityDeclaration(
                name="repository_generation",
                python_module="repoctl.modules.repository_generation",
                status="draft",
                proof_catalog="proof/repoctl/repository-generation.toml",
                inbound=(),
                outbound=(),
                api="repoctl.modules.repository_generation.api",
                factory="",
                cli_catalog="",
            ),
        ),
        ownership_zones=default_ownership_zones("acme"),
        approved_system_modules=SYSTEM_CAPABILITY_MODULES,
    )

    assert compilation.source_state_sha256 == (
        "4fea77788e9666e6b12698b9b4fac85af160db00472e83339460edfddc9f152e"
    )


def test_system_module_must_belong_to_the_declared_capability_name() -> None:
    with pytest.raises(DerivedIndexRenderingError, match="configured product or system capability"):
        _ = render_derived_indexes(
            package="acme",
            declarations=(
                _declaration(
                    name="alpha",
                    python_module="repoctl.modules.repository_generation",
                    status="active",
                ),
            ),
            ownership_zones=default_ownership_zones("acme"),
            approved_system_modules=SYSTEM_CAPABILITY_MODULES,
        )


def test_renderer_rejects_hard_keywords_but_allows_soft_keywords() -> None:
    def render_with_factory(factory: str) -> tuple[tuple[object, str], ...]:
        return render_derived_indexes(
            package="acme",
            declarations=(
                _declaration(
                    name="alpha",
                    python_module="acme.modules.alpha",
                    status="active",
                    factory=factory,
                ),
            ),
            ownership_zones=default_ownership_zones("acme"),
            approved_system_modules=SYSTEM_CAPABILITY_MODULES,
        ).writes

    with pytest.raises(DerivedIndexRenderingError, match="cannot be rendered"):
        _ = render_with_factory("acme.modules.alpha:class")

    assert any(
        "from acme.modules.alpha import match as build_alpha" in content
        for _, content in render_with_factory("acme.modules.alpha:match")
    )
