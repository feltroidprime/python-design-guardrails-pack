"""Tests for the None-discipline guard rules (ARCH016-ARCH018).

The template's own gate proves the rules pass on clean code (via
test_generated_architecture_guard_runs_and_passes); these tests prove each
rule fires on planted violations and stays silent on legitimate idioms.
They go through architecture_guard.check_file so the composition under test
is the shipped one: single parse, all rule families, central marker handling.
"""

from pathlib import Path

import pytest

# Import paths are provided by tests/conftest.py.
from scripts.architecture_guard import check_file
from scripts.architecture_policy import Policy, load_policy

TEMPLATE = Path(__file__).resolve().parents[1] / "template"


@pytest.fixture
def policy(tmp_path: Path) -> Policy:
    """The template's real policy, instantiated for a package named `pkg`."""
    manifest = (TEMPLATE / "architecture.toml.jinja").read_text(encoding="utf-8")
    (tmp_path / "architecture.toml").write_text(
        manifest.replace("{{ package }}", "pkg"), encoding="utf-8"
    )
    return load_policy(tmp_path)


def run_check(policy: Policy, relative: str, source: str) -> list[str]:
    path = policy.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return [item.code for item in check_file(path, policy)]


def test_arch016_fires_on_none_defaulted_collection_field(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/application/use_cases.py",
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Command:\n"
        "    tags: list[str] | None = None\n",
    )
    assert codes == ["ARCH016"]


def test_arch016_fires_on_module_level_collection_default(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/cache.py",
        "_cache: dict[str, int] | None = None\n",
    )
    assert codes == ["ARCH016"]


def test_arch016_ignores_non_collection_optionals_outside_domain(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/inbound/dto.py",
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class RawReading:\n"
        "    battery: float | None = None\n",
    )
    assert codes == []


def test_arch016_ignores_function_local_optionals(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/search.py",
        "def scan(items: list[int]) -> int:\n"
        "    found: list[int] | None = None\n"
        "    return len(found or items)\n",
    )
    assert codes == []


def test_arch017_fires_on_optional_domain_field(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Drone:\n"
        "    location: str | None\n",
    )
    assert codes == ["ARCH017"]


def test_arch017_fires_on_typing_optional_spelling(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        "from dataclasses import dataclass\n"
        "from typing import Optional\n"
        "@dataclass\n"
        "class Drone:\n"
        "    location: Optional[str]\n",
    )
    assert "ARCH017" in codes


def test_arch016_and_arch017_both_fire_on_optional_domain_collection(policy: Policy) -> None:
    """Pin the additive composition: a future first-match-wins refactor must not
    silently drop one of the two complementary findings."""
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Delivery:\n"
        "    avoid_zones: list[str] | None = None\n",
    )
    assert sorted(codes) == ["ARCH016", "ARCH017"]


def test_arch018_fires_on_optional_domain_return(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/routing.py",
        "def assign_route(capacity: int) -> str | None:\n"
        "    return 'route' if capacity else None\n",
    )
    assert codes == ["ARCH018"]


def test_optional_port_returns_stay_legal_outside_domain(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/application/ports.py",
        "from typing import Protocol\n"
        "class ItemRepository(Protocol):\n"
        "    def get(self, item_id: str) -> str | None: ...\n",
    )
    assert codes == []


def test_inline_exception_marker_suppresses_a_finding(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Drone:\n"
        "    location: str | None  # ARCH-EXCEPTION: ADR-0099\n",
    )
    assert codes == []


def test_unparsable_module_reports_arch000(policy: Policy) -> None:
    codes = run_check(policy, "src/pkg/domain/broken.py", "def broken(:\n")
    assert codes == ["ARCH000"]
