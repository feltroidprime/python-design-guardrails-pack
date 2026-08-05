"""Tests for the path-discipline guard rules (ARCH019-ARCH020).

The repository's own gate proves the rules pass on clean code; these tests
prove each rule fires on planted violations and stays silent on legitimate
idioms.
They go through architecture_guard.check_file so the composition under test
is the shipped one: single parse, all rule families, central marker handling.
"""

from pathlib import Path

import pytest

from scripts.architecture_guard import check_files
from scripts.architecture_policy import Policy, load_policy
from tests.policy_tree import write_policy_tree

PACK = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy(tmp_path: Path) -> Policy:
    """The repository's real policy, instantiated for a package named `pkg`."""
    return load_policy(write_policy_tree(tmp_path))


def run_check(policy: Policy, relative: str, source: str) -> list[str]:
    path = policy.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return [item.code for item in check_files((path,), policy)]


def test_arch019_fires_on_str_path_parameter(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/exporter.py",
        "def export(config_file: str) -> None:\n    print(config_file)\n",
    )
    assert codes == ["ARCH019"]


def test_arch019_fires_on_str_or_path_union(policy: Policy) -> None:
    """`str | Path` re-imports the ambiguity ARCH019 exists to remove."""
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/exporter.py",
        "from pathlib import Path\n"
        "def export(output_dir: str | Path) -> None:\n"
        "    print(output_dir)\n",
    )
    assert codes == ["ARCH019"]


def test_arch019_fires_on_path_named_return(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/layout.py",
        "def cache_dir(name: str) -> str:\n    return name\n",
    )
    assert codes == ["ARCH019"]


def test_arch019_fires_on_keyword_only_collection_of_paths(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/batch.py",
        "def load(*, paths: list[str]) -> None:\n    print(paths)\n",
    )
    assert codes == ["ARCH019"]


def test_arch019_checks_mapping_keys_but_not_mapping_values(policy: Policy) -> None:
    """`files: dict[Path, str]` maps paths to file content; only the key
    position carries the path (the template's diagram sync is the exemplar)."""
    silent = run_check(
        policy,
        "src/pkg/adapters/outbound/writer.py",
        "from pathlib import Path\n"
        "def write_files(files: dict[Path, str]) -> None:\n"
        "    print(files)\n",
    )
    fires = run_check(
        policy,
        "src/pkg/adapters/outbound/reader.py",
        "def read_files(files: dict[str, bytes]) -> None:\n    print(files)\n",
    )
    assert (silent, fires) == ([], ["ARCH019"])


def test_arch020_fires_on_str_path_class_field(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/settings.py",
        "from dataclasses import dataclass\n@dataclass\nclass Settings:\n    data_dir: str\n",
    )
    assert codes == ["ARCH020"]


def test_arch020_fires_on_module_level_path_constant(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/layout.py",
        'CACHE_DIR: str = "/tmp/cache"\n',
    )
    assert codes == ["ARCH020"]


def test_path_typed_declarations_stay_silent(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/exporter.py",
        "from dataclasses import dataclass\n"
        "from pathlib import Path\n"
        "@dataclass\n"
        "class Export:\n"
        "    output_dir: Path\n"
        "def export(config_file: Path) -> Path:\n"
        "    return config_file\n",
    )
    assert codes == []


def test_token_matching_never_matches_substrings(policy: Policy) -> None:
    """`profile`, `dirty`, and `file_format` contain path-ish substrings only."""
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/rendering.py",
        "def render(profile: str, file_format: str) -> None:\n"
        "    dirty: str = profile + file_format\n"
        "    print(dirty)\n",
    )
    assert codes == []


def test_bare_name_renamed_to_stem_stays_silent(policy: Policy) -> None:
    """Ladder rule: a value with no directory meaning is named for what it is."""
    codes = run_check(
        policy,
        "src/pkg/domain/naming.py",
        "def artifact_stem(label: str) -> str:\n    return label.lower()\n",
    )
    assert codes == []


def test_inline_exception_marker_suppresses_a_finding(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/exporter.py",
        "def export(\n"
        "    config_file: str,  # ARCH-EXCEPTION: ADR-0099\n"
        ") -> None:\n"
        "    print(config_file)\n",
    )
    assert codes == []
