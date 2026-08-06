"""The six `import-linter` contracts, on a tree with two example capabilities.

The clean tree is one package with two capabilities in the layout AGENTS.md
requires: `api.py`, `domain/`, `application/`, `adapters/inbound/`,
`adapters/outbound/`, `proof.toml` and `tests/`.

Each defect is the clean tree with one injected fault. The five faults are
the five ways a capability can break the layout rule. Each one must break a
contract, so the six contracts together carry the rules that the deleted
capability validator carried.
"""

from collections.abc import Callable
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.import_contracts import CONFIG_TEMPLATE, lint_imports_command, render

type Injection = Callable[[Path], None]

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "demo"
CAPABILITIES = ("alpha", "beta")
LAYER_DIRECTORIES = ("domain", "application", "adapters", "adapters/inbound", "adapters/outbound")

API_SOURCE = '''"""The public command surface of one capability."""


def report() -> str:
    """Return one line."""
    return "ok"
'''
COMPOSITION_SOURCE = "CAPABILITIES: tuple[object, ...] = ()\n"
CLI_SOURCE = "def main() -> int:\n    return 0\n"


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(source, encoding="utf-8")


def _write_capability(package_root: Path, name: str) -> None:
    capability = package_root / name
    _write(capability / "__init__.py", f'"""The {name} capability."""\n')
    _write(capability / "api.py", API_SOURCE)
    _write(capability / "proof.toml", "schema_version = 1\n")
    for layer in LAYER_DIRECTORIES:
        _write(capability / layer / "__init__.py", f'"""The {layer} layer."""\n')
    _write(capability / "tests" / "__init__.py", '"""The tests of one capability."""\n')


def clean_tree(root: Path) -> Path:
    """One package, two capabilities, and the two user-owned seams."""
    package_root = root / "src" / PACKAGE
    _write(package_root / "__init__.py", '"""The import package."""\n')
    _write(package_root / "_foundation" / "__init__.py", '"""The pack-owned foundation."""\n')
    _write(package_root / "cli.py", CLI_SOURCE)
    _write(package_root / "composition.py", COMPOSITION_SOURCE)
    for name in CAPABILITIES:
        _write_capability(package_root, name)
    return package_root


def run_contracts(root: Path) -> subprocess.CompletedProcess[str]:
    """Render the six contracts for this tree and run `lint-imports` on them."""
    template = (REPOSITORY_ROOT / CONFIG_TEMPLATE).read_text(encoding="utf-8")
    config = root / "importlinter.ini"
    _ = config.write_text(render(template, PACKAGE, CAPABILITIES), encoding="utf-8")
    return subprocess.run(
        (lint_imports_command(), "--config", str(config)),
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": str(Path(sys.executable).parent), "PYTHONPATH": str(root / "src")},
    )


def test_the_six_contracts_pass_on_two_example_capabilities(tmp_path: Path) -> None:
    _ = clean_tree(tmp_path)

    completed = run_contracts(tmp_path)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_the_rendered_containers_name_only_the_discovered_capabilities() -> None:
    """`FSC-7`: a wildcard container would also match cli, composition and _foundation."""
    template = (REPOSITORY_ROOT / CONFIG_TEMPLATE).read_text(encoding="utf-8")

    config = render(template, PACKAGE, CAPABILITIES)

    containers = config[config.index("containers =") :].splitlines()[1:3]
    assert [line.strip() for line in containers] == ["demo.alpha", "demo.beta"]


def _delete_the_domain_layer(package_root: Path) -> None:
    """`FSC-1`: a capability layer is missing."""
    (package_root / "alpha" / "domain" / "__init__.py").unlink()
    (package_root / "alpha" / "domain").rmdir()


def _empty_the_domain_layer(package_root: Path) -> None:
    """`FSC-2`: a layer directory holds no module, which counts as missing."""
    (package_root / "alpha" / "domain" / "__init__.py").unlink()


def _import_a_sibling_capability(package_root: Path) -> None:
    """`FSC-3`: a capability imports a sibling capability."""
    _write(
        package_root / "alpha" / "api.py",
        f"from {PACKAGE}.beta import api\n\n{API_SOURCE}",
    )


def _reach_a_capability_internal(package_root: Path) -> None:
    """`FSC-4`: the composition root reaches past the public surface."""
    _write(
        package_root / "composition.py",
        f"from {PACKAGE}.alpha import domain\n\n{COMPOSITION_SOURCE}",
    )


def _import_pack_code(package_root: Path) -> None:
    """`FSC-5`: a capability imports the pack-owned foundation."""
    _write(
        package_root / "alpha" / "api.py",
        f"from {PACKAGE} import _foundation\n\n{API_SOURCE}",
    )


MISSING_LAYER = "Missing layer in container 'demo.alpha'"


@pytest.mark.parametrize(
    ("assertion_id", "inject", "reported"),
    [
        ("FSC-1", _delete_the_domain_layer, MISSING_LAYER),
        ("FSC-2", _empty_the_domain_layer, MISSING_LAYER),
        ("FSC-3", _import_a_sibling_capability, "Capabilities are independent BROKEN"),
        ("FSC-4", _reach_a_capability_internal, "Capability internals are private BROKEN"),
        ("FSC-5", _import_pack_code, "The foundation is pack owned BROKEN"),
    ],
)
def test_each_injected_defect_breaks_a_contract(
    tmp_path: Path,
    assertion_id: str,
    inject: Injection,
    reported: str,
) -> None:
    package_root = clean_tree(tmp_path)
    inject(package_root)

    completed = run_contracts(tmp_path)

    assert completed.returncode != 0, f"{assertion_id} did not break a contract"
    assert reported in " ".join(completed.stdout.split()), completed.stdout
