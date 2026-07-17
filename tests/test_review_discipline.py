"""Tests for review-harvest architecture rules (ARCH026-ARCH030)."""

from pathlib import Path

import pytest

# Import paths are provided by tests/conftest.py.
from scripts.architecture_guard import check_files
from scripts.architecture_policy import Policy, load_policy

TEMPLATE = Path(__file__).resolve().parents[1] / "template"

ARCH026_VIOLATING_FIXTURE = """\
PENDING: list[str] = ["one"]
LOOKUP = {"one": 1}
SEEN = set()
QUEUE = list()
INDEX = dict()
FLAGS = {"ready"}
if True:
    CONDITIONAL = []
__all__ = set()
"""

ARCH026_CLEAN_FIXTURE = """\
from typing import Final

PENDING: Final = ("one",)
LOOKUP = frozenset({"one"})
__all__ = ["PENDING", "LOOKUP"]

def collect() -> tuple[str, ...]:
    local = ["one"]
    return tuple(local)
"""

ARCH027_VIOLATING_FIXTURES = (
    (
        "src/pkg/first.py",
        """\
from enum import StrEnum

class DeliveryState(StrEnum):
    PENDING = "pending"
    READY = "ready"
""",
    ),
    (
        "src/pkg/second.py",
        """\
from enum import StrEnum

class DeliveryState(StrEnum):
    PENDING = "pending"
    READY = "ready"
""",
    ),
)

ARCH027_CLEAN_FIXTURES = (
    (
        "src/pkg/delivery.py",
        """\
from enum import StrEnum

class DeliveryState(StrEnum):
    PENDING = "pending"
    READY = "ready"
""",
    ),
    (
        "src/pkg/payment.py",
        """\
from enum import StrEnum

class PaymentState(StrEnum):
    PENDING = "pending"
    READY = "ready"
""",
    ),
)

ARCH028_VIOLATING_FIXTURE = """\
from dataclasses import dataclass
from pathlib import Path

def load(relative: str) -> Path:
    return Path(relative)

@dataclass
class Evidence:
    evidence: str

    def read(self) -> str:
        return Path(self.evidence).read_text()
"""

ARCH028_CLEAN_FIXTURE = """\
from dataclasses import dataclass
from pathlib import Path

def load(relative: Path) -> Path:
    return Path(relative)

@dataclass
class Evidence:
    evidence: Path

    def read(self) -> str:
        return self.evidence.read_text()

def open_evidence(source: Path, mode: str, encoding: str) -> object:
    return open(source, mode, encoding=encoding)
"""

ARCH029_VIOLATING_FIXTURE = """\
from typing import TypeAlias

ApiBindHost = str
LegacyBindHost: TypeAlias = str

def bind(host: ApiBindHost) -> None:
    print(host)

def bind_legacy(host: LegacyBindHost) -> None:
    print(host)
"""

ARCH029_CLEAN_FIXTURE = """\
from typing import Literal

type ApiBindHost = Literal["loopback", "all-interfaces"]
JsonString = str

def bind(host: ApiBindHost) -> None:
    print(host)

def serialize(value: JsonString) -> str:
    return value
"""

ARCH030_VIOLATING_FIXTURES = (
    (
        "src/pkg/ports.py",
        """\
from typing import Protocol

class EvidenceWriter(Protocol):
    def write(self, evidence: str) -> None: ...
""",
    ),
    (
        "src/pkg/writer.py",
        """\
from pkg.ports import EvidenceWriter

class FileEvidenceWriter(EvidenceWriter):
    def write(self, evidence: str) -> None:
        print(evidence)
""",
    ),
)

ARCH030_CLEAN_FIXTURES = (
    ARCH030_VIOLATING_FIXTURES[0],
    (
        "src/pkg/writer.py",
        """\
from typing import override

from pkg.ports import EvidenceWriter

class FileEvidenceWriter(EvidenceWriter):
    @override
    def write(self, evidence: str) -> None:
        print(evidence)
""",
    ),
)


@pytest.fixture
def policy(tmp_path: Path) -> Policy:
    """The template's real policy, instantiated for a package named `pkg`."""
    manifest = (TEMPLATE / "architecture.toml.jinja").read_text(encoding="utf-8")
    (tmp_path / "architecture.toml").write_text(
        manifest.replace("{{ package }}", "pkg"), encoding="utf-8"
    )
    return load_policy(tmp_path)


def run_check(policy: Policy, relative: str, source: str) -> list[tuple[str, str]]:
    path = policy.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return [(item.code, item.message) for item in check_files((path,), policy)]


def run_repository_check(
    policy: Policy, fixtures: tuple[tuple[str, str], ...]
) -> list[tuple[str, str, str]]:
    paths: list[Path] = []
    for relative, source in fixtures:
        path = policy.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        paths.append(path)
    return [
        (item.path.relative_to(policy.root).as_posix(), item.code, item.message)
        for item in check_files(paths, policy)
    ]


def test_arch026_rejects_mutable_module_state(policy: Policy) -> None:
    violations = run_check(
        policy,
        "tests/test_catalog.py",
        ARCH026_VIOLATING_FIXTURE,
    )
    assert violations == [
        (
            "ARCH026",
            "Module variable 'PENDING' owns mutable state; use an immutable value.",
        ),
        (
            "ARCH026",
            "Module variable 'LOOKUP' owns mutable state; use an immutable value.",
        ),
        (
            "ARCH026",
            "Module variable 'SEEN' owns mutable state; use an immutable value.",
        ),
        (
            "ARCH026",
            "Module variable 'QUEUE' owns mutable state; use an immutable value.",
        ),
        (
            "ARCH026",
            "Module variable 'INDEX' owns mutable state; use an immutable value.",
        ),
        (
            "ARCH026",
            "Module variable 'FLAGS' owns mutable state; use an immutable value.",
        ),
        (
            "ARCH026",
            "Module variable 'CONDITIONAL' owns mutable state; use an immutable value.",
        ),
        (
            "ARCH026",
            "Module variable '__all__' owns mutable state; use an immutable value.",
        ),
    ]


def test_arch026_accepts_immutable_state_all_and_locals(policy: Policy) -> None:
    assert (
        run_check(
            policy,
            "tests/test_catalog.py",
            ARCH026_CLEAN_FIXTURE,
        )
        == []
    )


def test_arch027_rejects_duplicate_in_repository_models(policy: Policy) -> None:
    violations = run_repository_check(policy, ARCH027_VIOLATING_FIXTURES)
    assert violations == [
        (
            "src/pkg/second.py",
            "ARCH027",
            "Model 'DeliveryState' is duplicated; keep one owner.",
        )
    ]


def test_arch027_accepts_distinct_concepts_with_the_same_variants(
    policy: Policy,
) -> None:
    assert run_repository_check(policy, ARCH027_CLEAN_FIXTURES) == []


def test_arch028_rejects_untokenized_str_values_used_as_paths(policy: Policy) -> None:
    violations = run_check(
        policy,
        "src/pkg/adapters/outbound/evidence.py",
        ARCH028_VIOLATING_FIXTURE,
    )
    assert violations == [
        (
            "ARCH028",
            "Parameter 'relative' is str used as a filesystem path; declare pathlib.Path.",
        ),
        (
            "ARCH028",
            "Field 'evidence' is str used as a filesystem path; declare pathlib.Path.",
        ),
    ]


def test_arch028_accepts_path_typed_untokenized_values(policy: Policy) -> None:
    assert (
        run_check(
            policy,
            "src/pkg/adapters/outbound/evidence.py",
            ARCH028_CLEAN_FIXTURE,
        )
        == []
    )


@pytest.mark.parametrize(
    "use",
    [
        "Path(evidence)",
        "open(evidence)",
        "os.fspath(evidence)",
        "evidence.read_text()",
        "evidence.write_text('value')",
        "pathlib.PurePath(evidence)",
    ],
)
def test_arch028_recognizes_supported_path_uses(policy: Policy, use: str) -> None:
    violations = run_check(
        policy,
        "src/pkg/adapters/outbound/evidence.py",
        "import os\nimport pathlib\nfrom pathlib import Path\n"
        f"def handle(evidence: str) -> object:\n    return {use}\n",
    )
    assert [code for code, _message in violations] == ["ARCH028"]


def test_arch028_does_not_double_report_arch019_names(policy: Policy) -> None:
    violations = run_check(
        policy,
        "src/pkg/adapters/outbound/evidence.py",
        "from pathlib import Path\n"
        "def handle(config_file: str) -> Path:\n"
        "    return Path(config_file)\n",
    )
    assert [code for code, _message in violations] == ["ARCH019"]


def test_arch029_rejects_used_domain_aliases_to_bare_primitives(policy: Policy) -> None:
    violations = run_check(
        policy,
        "src/pkg/adapters/inbound/api.py",
        ARCH029_VIOLATING_FIXTURE,
    )
    assert violations == [
        (
            "ARCH029",
            "Domain type 'ApiBindHost' is bare str; define a closed variant.",
        ),
        (
            "ARCH029",
            "Domain type 'LegacyBindHost' is bare str; define a closed variant.",
        ),
    ]


def test_arch029_accepts_closed_variants_and_allowlisted_wire_scalars(
    policy: Policy,
) -> None:
    assert (
        run_check(
            policy,
            "src/pkg/adapters/inbound/api.py",
            ARCH029_CLEAN_FIXTURE,
        )
        == []
    )


def test_arch030_rejects_unmarked_in_repository_overrides(policy: Policy) -> None:
    violations = run_repository_check(policy, ARCH030_VIOLATING_FIXTURES)
    assert violations == [
        (
            "src/pkg/writer.py",
            "ARCH030",
            "Method 'FileEvidenceWriter.write' overrides a base; add @override.",
        )
    ]


def test_arch030_accepts_marked_in_repository_overrides(policy: Policy) -> None:
    assert run_repository_check(policy, ARCH030_CLEAN_FIXTURES) == []


def test_arch030_does_not_resolve_an_external_base_by_simple_name(
    policy: Policy,
) -> None:
    fixtures = (
        ("src/pkg/base.py", "class Base:\n    def run(self) -> None: ...\n"),
        (
            "src/pkg/child.py",
            "from external import Base\n"
            "class Child(Base):\n"
            "    def run(self) -> None:\n"
            "        pass\n",
        ),
    )
    assert run_repository_check(policy, fixtures) == []


def test_arch026_through_arch030_share_adr_backed_marker_suppression(
    policy: Policy,
) -> None:
    arch026 = run_check(
        policy,
        "tests/test_catalog.py",
        "VALUES = []  # ARCH-EXCEPTION: ADR-0099\n",
    )
    arch027 = run_repository_check(
        policy,
        (
            (
                "src/pkg/first.py",
                "from enum import Enum\nclass State(Enum):\n    READY = 'ready'\n",
            ),
            (
                "src/pkg/second.py",
                "from enum import Enum\n"
                "class State(Enum):  # ARCH-EXCEPTION: ADR-0099\n"
                "    READY = 'ready'\n",
            ),
        ),
    )
    arch028 = run_check(
        policy,
        "src/pkg/evidence.py",
        "from pathlib import Path\n"
        "def load(evidence: str) -> Path:  # ARCH-EXCEPTION: ADR-0099\n"
        "    return Path(evidence)\n",
    )
    arch029 = run_check(
        policy,
        "src/pkg/api.py",
        "ApiBindHost = str  # ARCH-EXCEPTION: ADR-0099\n"
        "def bind(host: ApiBindHost) -> None: ...\n",
    )
    arch030 = run_repository_check(
        policy,
        (
            ("src/pkg/base.py", "class Base:\n    def run(self) -> None: ...\n"),
            (
                "src/pkg/child.py",
                "from pkg.base import Base\n"
                "class Child(Base):\n"
                "    def run(self) -> None:  # ARCH-EXCEPTION: ADR-0099\n"
                "        pass\n",
            ),
        ),
    )
    assert (arch026, arch027, arch028, arch029, arch030) == ([], [], [], [], [])
