"""Write one filesystem-native capability into a tree, and inject one defect.

Group 5 builds each `DEFECT` tree by adding one capability to `TERM` and
breaking exactly one rule of it. This module writes the clean capability and the
five injections, so each assertion states the defect and reads the gate.

The capability is the shape that layout rule 1 states: one directory under the
package, holding `api.py`, `domain/`, `application/`, `adapters/inbound/`,
`adapters/outbound/`, `proof.toml` and `tests/`. There is no container directory
and no nesting.

The five capability shapes in `fixtures/shapes/` are the worked examples of
that layout. They are read by a maintainer, never by the gate, so a Terminal
Project ships no product exemplar.
"""

from pathlib import Path

__all__ = [
    "LAYERS",
    "add_capability",
    "compose",
    "delete_layer",
    "delete_proof",
    "empty_layer",
    "import_a_sibling",
    "import_pack_code",
    "reach_an_internal",
]

SOURCE_DIRECTORY = "src"
LAYERS = ("domain", "application", "adapters", "adapters/inbound", "adapters/outbound")
COMPOSITION = "composition.py"
PROOF_FILE = "proof.toml"
API_FILE = "api.py"
INITIALIZER = "__init__.py"
# The proof catalog of one capability that declares no property yet. The key
# below is what the catalog schema requires; the two ban lists of `LEG-1` also
# hold it, which is a conflict that ticket I11 has to settle for the whole tree.
PROOF_SOURCE = "schema_version = 1\n"
API_SOURCE = '"""The public command surface of one capability."""\n'
COMPOSED = "CAPABILITIES: tuple[object, ...] = ({name}_api,)\n"
EMPTY_TUPLE = "CAPABILITIES: tuple[object, ...] = ()\n"


def _write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(source, encoding="utf-8")
    return path


def capability_root(tree: Path, package: str, name: str) -> Path:
    """Where one capability sits: directly under the package, with no container."""
    return tree / SOURCE_DIRECTORY / package / name


def add_capability(tree: Path, package: str, name: str, *, api: str = API_SOURCE) -> Path:
    """Write one clean capability of the layout that `AGENTS.md` states."""
    root = capability_root(tree, package, name)
    _ = _write(root / INITIALIZER, f'"""The {name} capability."""\n')
    _ = _write(root / API_FILE, api)
    _ = _write(root / PROOF_FILE, PROOF_SOURCE)
    for layer in LAYERS:
        _ = _write(root / layer / INITIALIZER, f'"""The {layer} layer of {name}."""\n')
    _ = _write(root / "tests" / INITIALIZER, f'"""The tests of {name}."""\n')
    return root


def compose(tree: Path, package: str, name: str) -> Path:
    """Add the one import line that composes a capability into the product."""
    root = tree / SOURCE_DIRECTORY / package / COMPOSITION
    return _write(
        root,
        f"from {package}.{name} import api as {name}_api\n\n{COMPOSED.format(name=name)}",
    )


def delete_layer(tree: Path, package: str, name: str, layer: str = "domain") -> None:
    """`FSC-1`: one declared layer of the capability is absent."""
    root = capability_root(tree, package, name) / layer
    for item in sorted(root.rglob("*"), reverse=True):
        item.unlink()
    root.rmdir()


def empty_layer(tree: Path, package: str, name: str, layer: str = "domain") -> None:
    """`FSC-2`: the layer directory exists and holds no module, which counts as absent."""
    (capability_root(tree, package, name) / layer / INITIALIZER).unlink()


def import_a_sibling(tree: Path, package: str, name: str, sibling: str) -> None:
    """`FSC-3`: one capability imports a sibling capability."""
    api = capability_root(tree, package, name) / API_FILE
    _ = _write(
        api,
        f'"""One capability that reaches a sibling."""\n\nfrom {package}.{sibling} import api\n\n__all__ = ["api"]\n',
    )


def reach_an_internal(tree: Path, package: str, name: str) -> None:
    """`FSC-4`: the composition root reaches past the public surface."""
    root = tree / SOURCE_DIRECTORY / package / COMPOSITION
    _ = _write(root, f"from {package}.{name} import domain\n\n{EMPTY_TUPLE}")


def import_pack_code(tree: Path, package: str, name: str) -> None:
    """`FSC-5`: one capability imports the pack-owned foundation."""
    api = capability_root(tree, package, name) / API_FILE
    _ = _write(
        api,
        f'"""One capability that reaches pack code."""\n\nfrom {package} import _foundation\n\n__all__ = ["_foundation"]\n',
    )


def delete_proof(tree: Path, package: str, name: str) -> None:
    """`FSC-8`: the capability carries no proof catalog of its own."""
    (capability_root(tree, package, name) / PROOF_FILE).unlink()
