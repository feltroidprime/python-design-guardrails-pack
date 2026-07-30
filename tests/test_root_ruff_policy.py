"""The pack root and generated repositories share one Ruff policy."""

from pathlib import Path
import re
import tomllib

import instantiate

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROOT_PYPROJECT = REPOSITORY_ROOT / "pyproject.toml"
JUSTFILE = REPOSITORY_ROOT / "justfile"
RUFF_FLOOR = re.compile(r"ruff>=([0-9.]+)")


def load_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def ruff_configuration(document: dict[str, object]) -> dict[str, object]:
    tool = document["tool"]
    assert isinstance(tool, dict)
    ruff = tool["ruff"]
    assert isinstance(ruff, dict)
    return ruff


def test_root_ruff_policy_matches_a_generated_repository(tmp_path: Path) -> None:
    generated = tmp_path / "orchard-billing"
    error = instantiate.generate("orchard-billing", "orchard_billing", generated)
    assert error is None

    root = ruff_configuration(load_toml(ROOT_PYPROJECT))
    downstream = ruff_configuration(load_toml(generated / "pyproject.toml"))

    assert root["line-length"] == downstream["line-length"]
    assert root["force-exclude"] == downstream["force-exclude"]
    assert root["format"] == downstream["format"]

    root_lint = root["lint"]
    downstream_lint = downstream["lint"]
    assert isinstance(root_lint, dict)
    assert isinstance(downstream_lint, dict)
    assert root_lint["select"] == downstream_lint["select"]
    for section in (
        "flake8-type-checking",
        "mccabe",
        "flake8-tidy-imports",
    ):
        assert root_lint[section] == downstream_lint[section]

    root_isort = root_lint["isort"]
    downstream_isort = downstream_lint["isort"]
    assert isinstance(root_isort, dict)
    assert isinstance(downstream_isort, dict)
    assert root_isort["combine-as-imports"] == downstream_isort["combine-as-imports"]
    assert (
        root_isort["force-sort-within-sections"] == downstream_isort["force-sort-within-sections"]
    )


def test_rendered_symbolic_canary_has_ruff_spacing(tmp_path: Path) -> None:
    generated = tmp_path / "canary-check"
    error = instantiate.generate("canary-check", "canary_check", generated)
    assert error is None

    canary = (generated / "verification" / "harness" / "symbolic_canary.py").read_text(
        encoding="utf-8"
    )
    assert "\n\n\n\ndef _denies_echo" not in canary
    assert "\n\n\ndef _denies_echo" in canary


def test_root_check_uses_the_generated_ruff_floor() -> None:
    root_justfile = JUSTFILE.read_text(encoding="utf-8")
    template_pyproject = (REPOSITORY_ROOT / "template" / "pyproject.toml.jinja").read_text(
        encoding="utf-8"
    )

    assert RUFF_FLOOR.findall(root_justfile) == RUFF_FLOOR.findall(template_pyproject)
    assert "test: check" in root_justfile
    assert "test-fast: check" in root_justfile
    assert 'ruff_sources := "instantiate.py scripts tests template"' in root_justfile
