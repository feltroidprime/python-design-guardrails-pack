"""Tests for the None-discipline guard rules (ARCH016-ARCH018).

The repository's own gate proves the rules pass on clean code; these tests
prove each rule fires on planted violations and stays silent on legitimate
idioms.
They go through architecture_guard.check_files so the composition under
test is the shipped one: single parse, all rule families, central marker
handling.
"""

from pathlib import Path

import pytest

from scripts.architecture_guard import check_files
from scripts.architecture_policy import Policy, load_policy
from tests.policy_tree import EXCEPTION_MARKER, write_policy_tree

PACK = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy(tmp_path: Path) -> Policy:
    """The repository's real policy, instantiated for a package named `pkg`."""
    return load_policy(write_policy_tree(tmp_path))


def run_check(policy: Policy, relative: str, source: str) -> list[str]:
    path = policy.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(source, encoding="utf-8")
    return [item.code for item in check_files((path,), policy)]


def test_arch016_fires_on_none_defaulted_collection_field(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/application/use_cases.py",
        """from dataclasses import dataclass
@dataclass
class Command:
    tags: list[str] | None = None
""",
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
        """from dataclasses import dataclass
@dataclass
class RawReading:
    battery: float | None = None
""",
    )
    assert codes == []


def test_arch016_ignores_function_local_optionals(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/adapters/outbound/search.py",
        """def scan(items: list[int]) -> int:
    found: list[int] | None = None
    return len(found or items)
""",
    )
    assert codes == []


def test_arch017_fires_on_optional_domain_field(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        """from dataclasses import dataclass
@dataclass(frozen=True, slots=True, kw_only=True)
class Drone:
    location: str | None
""",
    )
    assert codes == ["ARCH017"]


def test_arch017_fires_on_typing_optional_spelling(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        """from dataclasses import dataclass
from typing import Optional
@dataclass(frozen=True, slots=True, kw_only=True)
class Drone:
    location: Optional[str]
""",
    )
    assert "ARCH017" in codes


def test_arch016_and_arch017_both_fire_on_optional_domain_collection(policy: Policy) -> None:
    """Pin the additive composition: a future first-match-wins refactor must not
    silently drop one of the two complementary findings."""
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        """from dataclasses import dataclass
@dataclass(frozen=True, slots=True, kw_only=True)
class Delivery:
    avoid_zones: list[str] | None = None
""",
    )
    assert sorted(codes) == ["ARCH016", "ARCH017"]


def test_arch018_fires_on_optional_domain_return(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/routing.py",
        """def assign_route(capacity: int) -> str | None:
    return 'route' if capacity else None
""",
    )
    assert codes == ["ARCH018"]


def test_optional_port_returns_stay_legal_outside_domain(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/application/ports.py",
        """from typing import Protocol
class ItemRepository(Protocol):
    def get(self, item_id: str) -> str | None: ...
""",
    )
    assert codes == []


def test_inline_exception_marker_suppresses_a_finding(policy: Policy) -> None:
    codes = run_check(
        policy,
        "src/pkg/domain/entities.py",
        f"""from dataclasses import dataclass
@dataclass(frozen=True, slots=True, kw_only=True)
class Drone:
    location: str | None  # {EXCEPTION_MARKER}0099
""",
    )
    assert codes == []


def test_unparsable_module_reports_arch000(policy: Policy) -> None:
    codes = run_check(policy, "src/pkg/domain/broken.py", "def broken(:\n")
    assert codes == ["ARCH000"]
