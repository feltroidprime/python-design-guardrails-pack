"""The import-contract shim: what it discovers, and what it injects.

`pack/configs/importlinter.ini` carries every rule. The shim carries none. These
tests hold that split, and they hold the two measured facts that shape
the rendering: a wildcard container also matches `cli`, `composition` and
`_foundation`, and a project with no capability must render no layer contract.
"""

import configparser
from pathlib import Path

import pytest

from scripts.identity import DiscoveryError, discover_capabilities, discover_package
from scripts.import_contracts import CONFIG_TEMPLATE, render, rendered_config, repository_root

REPOSITORY_ROOT = repository_root()
CAPABILITY_CONTRACTS = (
    "importlinter:contract:capability-layers",
    "importlinter:contract:capability-public-surface",
    "importlinter:contract:capability-independence",
)
FIXED_CONTRACTS = (
    "importlinter:contract:foundation-is-pack-owned",
    "importlinter:contract:foundation-imports-only-composition",
    "importlinter:contract:domain-is-pure",
)
NEVER_A_CONTAINER = ("cli", "composition", "_foundation")


def template() -> str:
    return (REPOSITORY_ROOT / CONFIG_TEMPLATE).read_text(encoding="utf-8")


def parse(config: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read_string(config)
    return parser


def contract_names(config: configparser.ConfigParser) -> list[str]:
    sections: list[str] = list(config.sections())
    return sorted(name for name in sections if name.startswith("importlinter:contract:"))


def make_package(root: Path, package: str, capabilities: tuple[str, ...]) -> None:
    (root / "src" / package / "_foundation").mkdir(parents=True)
    for name in capabilities:
        (root / "src" / package / name).mkdir()


def test_the_template_declares_six_contracts() -> None:
    assert contract_names(parse(template())) == sorted(CAPABILITY_CONTRACTS + FIXED_CONTRACTS)


def test_the_shim_injects_the_discovered_capability_list() -> None:
    config = parse(render(template(), "demo", ("alpha", "beta")))

    containers = config["importlinter:contract:capability-layers"]["containers"].split()

    assert containers == ["demo.alpha", "demo.beta"]
    assert not any(name in " ".join(containers) for name in NEVER_A_CONTAINER)


def test_the_shim_injects_one_line_per_capability_in_every_capability_contract() -> None:
    config = parse(render(template(), "demo", ("alpha", "beta")))

    protected = config["importlinter:contract:capability-public-surface"]
    independent = config["importlinter:contract:capability-independence"]

    assert sorted(protected["protected_modules"].split()) == [
        "demo.alpha.adapters",
        "demo.alpha.application",
        "demo.alpha.domain",
        "demo.beta.adapters",
        "demo.beta.application",
        "demo.beta.domain",
    ]
    assert protected["allowed_importers"].split() == ["demo.alpha", "demo.beta"]
    assert independent["modules"].split() == ["demo.alpha", "demo.beta"]


def test_a_project_with_no_capability_renders_no_capability_contract() -> None:
    config = parse(render(template(), "demo", ()))

    assert contract_names(config) == sorted(FIXED_CONTRACTS)
    assert config["importlinter"]["root_package"] == "demo"


def test_no_directive_of_the_rendered_config_carries_a_token() -> None:
    """A comment explains each token, so only the directives must be free of one."""
    directives = [
        line
        for line in render(template(), "demo", ("alpha",)).splitlines()
        if line and not line.startswith(";")
    ]

    assert directives
    assert not [line for line in directives if "{package}" in line or "{capability}" in line]


def test_the_shim_reads_the_package_name_from_the_source_directory(tmp_path: Path) -> None:
    make_package(tmp_path, "demo", ())

    assert discover_package(tmp_path) == "demo"


def test_a_tree_without_exactly_one_package_is_refused(tmp_path: Path) -> None:
    make_package(tmp_path, "first", ())
    (tmp_path / "src" / "second").mkdir()

    with pytest.raises(DiscoveryError):
        _ = discover_package(tmp_path)


def test_an_empty_capability_directory_is_still_a_capability(tmp_path: Path) -> None:
    make_package(tmp_path, "demo", ("alpha",))

    assert discover_capabilities(tmp_path, "demo") == ("alpha",)


def test_a_private_directory_is_never_a_capability(tmp_path: Path) -> None:
    make_package(tmp_path, "demo", ())

    assert discover_capabilities(tmp_path, "demo") == ()


def test_this_repository_renders_a_readable_config() -> None:
    config = parse(rendered_config(REPOSITORY_ROOT))

    assert config["importlinter"]["root_package"] == discover_package(REPOSITORY_ROOT)
