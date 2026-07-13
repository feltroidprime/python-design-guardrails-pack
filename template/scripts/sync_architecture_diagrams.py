#!/usr/bin/env python3
"""Regenerate the derived LikeC4 architecture model from the import graph.

The architecture model is derived, never hand-maintained. Layers come from
the import-linter contracts in pyproject.toml and relationships come from
the real import graph reported by grimp — the same library import-linter
uses — so the diagrams and the linter cannot contradict each other.

Modes:
    --write  regenerate the files under docs/architecture/likec4/generated/
    --check  regenerate in memory and exit non-zero if the committed files
             differ, naming the exact command that fixes the drift

Output is deterministic: stable ordering, no timestamps.
"""

from dataclasses import dataclass
from pathlib import Path
import sys
import tomllib
from typing import cast

import grimp

from scripts.architecture_policy import mapping, string

GENERATED_DIR = Path("docs") / "architecture" / "likec4" / "generated"
MODEL_FILE = "model.c4"
VIEWS_FILE = "baseline-views.c4"
FIX_COMMAND = "uv run python -m scripts.sync_architecture_diagrams --write"
HEADER = (
    "// GENERATED FILE — do not edit by hand.\n"
    f"// Regenerate with 'just fix' (or: {FIX_COMMAND}).\n"
    "\n"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchitectureSource:
    """What pyproject.toml declares about the architecture."""

    project_name: str
    package: str
    layers: tuple[str, ...]
    independent_modules: frozenset[str]
    exclude_type_checking_imports: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivedModel:
    """The architecture model derived from the import graph."""

    project_name: str
    package: str
    layers: tuple[str, ...]
    modules: dict[str, tuple[str, ...]]
    independent_modules: frozenset[str]
    relationships: tuple[tuple[str, str], ...]


def string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be an array of strings")
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise TypeError(f"{name} must be an array of strings")
    return tuple(cast("list[str]", items))


def find_contract(contracts: object, contract_type: str) -> dict[str, object] | None:
    if not isinstance(contracts, list):
        raise TypeError("tool.importlinter.contracts must be an array of tables")
    for raw in cast("list[object]", contracts):
        contract = mapping(raw, "tool.importlinter.contracts[*]")
        if contract.get("type") == contract_type:
            return contract
    return None


def load_source(root: Path) -> ArchitectureSource:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    raw = mapping(tomllib.loads(pyproject), "pyproject.toml")
    project = mapping(raw["project"], "project")
    linter = mapping(mapping(raw["tool"], "tool")["importlinter"], "tool.importlinter")
    layers_contract = find_contract(linter["contracts"], "layers")
    if layers_contract is None:
        message = "pyproject.toml has no import-linter 'layers' contract to derive layers from."
        raise LookupError(message)
    independence = find_contract(linter["contracts"], "independence")
    independent = (
        string_list(independence["modules"], "independence contract modules")
        if independence is not None
        else ()
    )
    exclude = linter.get("exclude_type_checking_imports", False)
    if not isinstance(exclude, bool):
        raise TypeError("tool.importlinter.exclude_type_checking_imports must be a boolean")
    return ArchitectureSource(
        project_name=string(project["name"], "project.name"),
        package=string(linter["root_package"], "tool.importlinter.root_package"),
        layers=string_list(layers_contract["layers"], "layers contract layers"),
        independent_modules=frozenset(independent),
        exclude_type_checking_imports=exclude,
    )


def layer_short_names(source: ArchitectureSource) -> tuple[str, ...]:
    prefix = f"{source.package}."
    shorts: list[str] = []
    for layer in source.layers:
        short = layer.removeprefix(prefix)
        if short == layer or "." in short:
            message = f"Layer '{layer}' must be a direct child of '{source.package}'."
            raise ValueError(message)
        shorts.append(short)
    return tuple(shorts)


def build_import_graph(root: Path, source: ArchitectureSource) -> grimp.ImportGraph:
    source_root = str(root / "src")
    sys.path.insert(0, source_root)
    try:
        return grimp.build_graph(
            source.package,
            exclude_type_checking_imports=source.exclude_type_checking_imports,
            cache_dir=None,
        )
    finally:
        sys.path.remove(source_root)


def nearest_modeled(module: str, modeled: frozenset[str]) -> str | None:
    name = module
    while name not in modeled:
        if "." not in name:
            return None
        name = name.rsplit(".", maxsplit=1)[0]
    return name


def is_same_lineage(one: str, two: str) -> bool:
    return one == two or one.startswith(f"{two}.") or two.startswith(f"{one}.")


def derive_relationships(
    graph: grimp.ImportGraph, modeled: frozenset[str]
) -> tuple[tuple[str, str], ...]:
    pairs: set[tuple[str, str]] = set()
    for importer in graph.modules:
        for imported in graph.find_modules_directly_imported_by(importer):
            importing_element = nearest_modeled(importer, modeled)
            imported_element = nearest_modeled(imported, modeled)
            if importing_element is None or imported_element is None:
                continue
            if is_same_lineage(importing_element, imported_element):
                continue
            pairs.add((importing_element, imported_element))
    return tuple(sorted(pairs))


def derive_model(source: ArchitectureSource, graph: grimp.ImportGraph) -> DerivedModel:
    shorts = layer_short_names(source)
    modules: dict[str, tuple[str, ...]] = {}
    modeled: set[str] = {source.package}
    for short, full in zip(shorts, source.layers, strict=True):
        children = sorted(graph.find_children(full))
        modules[short] = tuple(child.rsplit(".", maxsplit=1)[-1] for child in children)
        modeled.add(full)
        modeled.update(children)
    return DerivedModel(
        project_name=source.project_name,
        package=source.package,
        layers=shorts,
        modules=modules,
        independent_modules=source.independent_modules,
        relationships=derive_relationships(graph, frozenset(modeled)),
    )


def render_module_element(model: DerivedModel, layer: str, child: str) -> list[str]:
    if f"{model.package}.{layer}.{child}" in model.independent_modules:
        return [
            f"      {child} = module '{child}' {{",
            "        #independent",
            "      }",
        ]
    return [f"      {child} = module '{child}'"]


def render_model(model: DerivedModel) -> str:
    lines = ["model {", f"  {model.package} = system '{model.project_name}' {{"]
    for layer in model.layers:
        children = model.modules[layer]
        if not children:
            lines.append(f"    {layer} = layer '{layer}'")
            continue
        lines.append(f"    {layer} = layer '{layer}' {{")
        for child in children:
            lines.extend(render_module_element(model, layer, child))
        lines.append("    }")
    lines.append("  }")
    if model.relationships:
        lines.append("")
        lines.extend(f"  {importer} -> {imported}" for importer, imported in model.relationships)
    lines.append("}")
    return HEADER + "\n".join(lines) + "\n"


def render_views(model: DerivedModel) -> str:
    lines = [
        "views {",
        f"  view index of {model.package} {{",
        f"    title '{model.project_name} — system overview'",
        "    include *",
        "  }",
    ]
    for layer in model.layers:
        lines.extend(
            (
                "",
                f"  view layer-{layer} of {model.package}.{layer} {{",
                f"    title 'Layer: {layer}'",
                "    include *",
                "  }",
            )
        )
    lines.append("}")
    return HEADER + "\n".join(lines) + "\n"


def generated_files(root: Path, model: DerivedModel) -> dict[Path, str]:
    directory = root / GENERATED_DIR
    return {
        directory / MODEL_FILE: render_model(model),
        directory / VIEWS_FILE: render_views(model),
    }


def write_files(root: Path, files: dict[Path, str]) -> int:
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(root)}")
    return 0


def check_files(root: Path, files: dict[Path, str]) -> int:
    stale = [
        path
        for path, expected in files.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != expected
    ]
    if not stale:
        print("Derived diagram files match the import graph.")
        return 0
    print("Derived diagram files are out of date with the code:", file=sys.stderr)
    for path in stale:
        print(f"  {path.relative_to(root)}", file=sys.stderr)
    print(f"FIX: run 'just fix' (or: {FIX_COMMAND})", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in {"--check", "--write"}:
        print("Usage: python -m scripts.sync_architecture_diagrams (--check | --write)")
        return 2
    root = Path(__file__).resolve().parents[1]
    source = load_source(root)
    model = derive_model(source, build_import_graph(root, source))
    files = generated_files(root, model)
    if argv[0] == "--write":
        return write_files(root, files)
    return check_files(root, files)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
