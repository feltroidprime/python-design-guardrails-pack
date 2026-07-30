from pathlib import Path
import tomllib

from jinja2 import Environment, StrictUndefined

import instantiate
from scripts.ownership import OwnershipZone, classify_path
from scripts.ownership_policy import OwnershipPolicy, load_ownership_policy

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPOSITORY_ROOT / "template"
ARCHITECTURE_SOURCE = TEMPLATE_ROOT / "architecture.toml.jinja"
PACKAGE = "product_probe"
CONTEXT = {
    "project_name": "product-root-probe",
    "package": PACKAGE,
    "agents_contract": "full",
    "workspace_member": False,
    "_copier_conf": {"answers_file": ".copier-answers.yml"},
}
PRODUCT_ROOT_PROBES = (
    TEMPLATE_ROOT / "src/{{ package }}/modules/placeholder.py",
    TEMPLATE_ROOT / "proof/modules/placeholder.toml",
    TEMPLATE_ROOT / "tests/modules/placeholder.py",
    TEMPLATE_ROOT / "verification/modules/placeholder.py",
)
EXAMPLE_MODULES = (
    f"{PACKAGE}.adapters.outbound.audit_log",
    f"{PACKAGE}.adapters.outbound.in_process_events",
    f"{PACKAGE}.adapters.outbound.memory_repository",
    f"{PACKAGE}.adapters.outbound.sqlite_repository",
    f"{PACKAGE}.adapters.outbound.system_clock",
    f"{PACKAGE}.adapters.outbound.uuid_ids",
    f"{PACKAGE}.application.idempotency",
    f"{PACKAGE}.application.query_models",
)
ITEM_CORE_PATHS = (
    Path("src") / PACKAGE / "application",
    Path("src") / PACKAGE / "domain",
)


def _generated_module_path(module: str) -> Path:
    return Path(*module.split(".")).with_suffix(".py")


def render_template_path(source: Path) -> Path | None:
    environment = Environment(undefined=StrictUndefined)
    rendered_parts = [
        environment.from_string(part).render(CONTEXT)
        for part in source.relative_to(TEMPLATE_ROOT).parts
    ]
    if any(not part for part in rendered_parts):
        return None
    rendered_parts[-1] = rendered_parts[-1].removesuffix(".jinja")
    return Path(*rendered_parts)


def ownership_policy(tmp_path: Path) -> OwnershipPolicy:
    environment = Environment(undefined=StrictUndefined)
    rendered = environment.from_string(ARCHITECTURE_SOURCE.read_text(encoding="utf-8")).render(
        CONTEXT
    )
    (tmp_path / "architecture.toml").write_text(rendered, encoding="utf-8")
    return load_ownership_policy(tmp_path)


def product_template_paths(
    sources: tuple[Path, ...],
    policy: OwnershipPolicy,
) -> tuple[Path, ...]:
    product = OwnershipZone("PRODUCT")
    matches: list[Path] = []
    for source in sources:
        rendered = render_template_path(source)
        if rendered is not None and classify_path(rendered, policy) == product:
            matches.append(source.relative_to(REPOSITORY_ROOT))
    return tuple(sorted(matches))


def test_template_never_renders_product_owned_files(tmp_path: Path) -> None:
    policy = ownership_policy(tmp_path)
    assert policy.source.relative_to(tmp_path) == ARCHITECTURE_SOURCE.relative_to(
        TEMPLATE_ROOT
    ).with_suffix("")
    template_sources = tuple(path for path in TEMPLATE_ROOT.rglob("*") if path.is_file())

    product_paths = product_template_paths(template_sources, policy)
    assert product_paths == (), (
        "Template files must never render into user-owned PRODUCT roots:\n"
        + "\n".join(path.as_posix() for path in product_paths)
    )

    detected_probes = product_template_paths(PRODUCT_ROOT_PROBES, policy)
    assert detected_probes == tuple(
        sorted(probe.relative_to(REPOSITORY_ROOT) for probe in PRODUCT_ROOT_PROBES)
    )


def test_generated_tree_has_no_example_adapter_or_brick_modules(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    assert instantiate.generate("ownership-zone-removal", PACKAGE, generated) is None

    present_modules = [
        module
        for module in EXAMPLE_MODULES
        if (generated / "src" / _generated_module_path(module)).exists()
    ]
    assert present_modules == []


def test_generated_tree_has_no_item_core_or_foundation_properties(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    assert instantiate.generate("item-core-removal", PACKAGE, generated) is None

    present_paths = [path for path in ITEM_CORE_PATHS if (generated / path).exists()]
    assert present_paths == []

    foundation_catalog = tomllib.loads(
        (generated / "proof" / "foundation.toml").read_text(encoding="utf-8")
    )
    assert "properties" not in foundation_catalog
