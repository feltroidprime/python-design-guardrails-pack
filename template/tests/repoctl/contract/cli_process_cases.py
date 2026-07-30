"""Declarative detached-process cases for the repository-control CLI."""

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import cast

from repoctl.modules.repository_generation.api import COMMAND_CATALOG, ControlCommandName


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _product_package() -> str:
    source_root = _project_root() / "src"
    packages = tuple(path.name for path in source_root.iterdir() if path.is_dir())
    assert len(packages) == 1, f"expected one generated product package, found {packages!r}"
    return packages[0]


PACKAGE = _product_package()


def _environment(project_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    previous_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(project_root), previous_pythonpath) if part
    )
    return environment


def run_repoctl(args: tuple[str, ...], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the public control command in a detached process with closed stdin."""
    project_root = _project_root()
    return subprocess.run(  # noqa: S603  # ARCH-EXCEPTION: ADR-0002
        [sys.executable, "-m", "repoctl", *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=_environment(project_root),
        text=True,
        timeout=10,
        check=False,
    )


@dataclass(slots=True, kw_only=True)
class ProcessContext:
    """One isolated filesystem and the detached commands used to prepare a case."""

    root: Path

    def run(self, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        """Run one precondition command through the same closed-stdin boundary."""
        return run_repoctl(args, cwd=self.root)

    def plan(self, *, name: str, destination: str) -> None:
        """Create one plan and require its public success outcome before continuing."""
        result = self.run(
            (
                "capability",
                "plan",
                name,
                "--inbound",
                "python",
                "--output",
                destination,
            )
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def write_product_file(self, *, name: str, leaf: str = "api.py") -> None:
        """Create an ordinary product file that changes the next planning snapshot."""
        path = self.root / "src" / PACKAGE / "modules" / name / leaf
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text('"""User-owned product surface."""\n', encoding="utf-8")

    def write_declaration(self, *, name: str, status: str) -> None:
        """Write one valid declaration so a query can observe bounded pagination."""
        path = self.root / ".repo" / "capabilities" / f"{name}.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(
            f'''schema_version = 1
name = "{name}"
python_module = "{PACKAGE}.modules.{name}"
status = "{status}"
proof_catalog = "proof/modules/{name}.toml"

[boundaries]
inbound = []
outbound = []

[activation]
api = "{PACKAGE}.modules.{name}.api"
factory = ""
cli_catalog = ""
''',
            encoding="utf-8",
        )

    def write_plan_control_file(self, *, destination: str) -> None:
        """Reserve one inspectable-plan destination without changing planning state."""
        path = self.root / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text('{"reserved":true}\n', encoding="utf-8")


type CaseSetup = Callable[[ProcessContext], None]
type DocumentAssertion = Callable[[dict[str, object]], None]


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessCase:
    """One public command outcome, including the isolated preconditions it needs."""

    identifier: str
    command: str
    catalog_command: ControlCommandName | None
    args: tuple[str, ...]
    setup: CaseSetup
    exit_code: int
    error_code: str | None
    assert_document: DocumentAssertion

    @property
    def success(self) -> bool:
        """Return whether this case describes one JSON success envelope."""
        return self.exit_code == 0


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _nothing(_document: dict[str, object]) -> None:
    """Express that the envelope and declared outcome fully specify this case."""


def _assert_empty_capabilities(document: dict[str, object]) -> None:
    data = _mapping(document["data"])
    metadata = _mapping(document["metadata"])
    assert data == {"capabilities": []}
    assert metadata == {"limit": 20, "truncated": False, "continuation": ""}


def _assert_status_without_prompt(document: dict[str, object]) -> None:
    data = _mapping(document["data"])
    repository = _mapping(data["repository"])
    assert repository == {"schema_version": 1, "package": PACKAGE}
    assert data["capability_counts"] == {"draft": 0, "active": 0, "retired": 0}


def _assert_plan_document(document: dict[str, object]) -> None:
    data = _mapping(document["data"])
    plan_document = _mapping(data["plan"])
    intent = _mapping(plan_document["intent"])
    assert intent == {"schema_version": 1, "name": "alpha", "inbound": ["python"], "outbound": []}


def _assert_already_applied(document: dict[str, object]) -> None:
    data = _mapping(document["data"])
    assert data["status"] == "already_applied"


def _assert_bounded_capabilities(document: dict[str, object]) -> None:
    data = _mapping(document["data"])
    metadata = _mapping(document["metadata"])
    capabilities = cast("list[object]", data["capabilities"])
    assert len(capabilities) == 1
    assert metadata["limit"] == 1
    assert metadata["truncated"] is True
    assert isinstance(metadata["continuation"], str)
    assert metadata["continuation"]


def _no_setup(_context: ProcessContext) -> None:
    """Leave a case's isolated repository empty."""


def _plan_alpha(context: ProcessContext) -> None:
    context.plan(name="alpha", destination=".repo/plans/alpha.json")


def _invalid_schema(context: ProcessContext) -> None:
    context.plan(name="alpha", destination=".repo/plans/source.json")
    source = context.root / ".repo" / "plans" / "source.json"
    target = context.root / ".repo" / "plans" / "invalid-schema.json"
    document = _mapping(cast("object", json.loads(source.read_text(encoding="utf-8"))))
    document["schema_version"] = 0
    _ = target.write_text(json.dumps(document), encoding="utf-8")


def _stale_plan(context: ProcessContext) -> None:
    _plan_alpha(context)
    context.write_product_file(name="manual")


def _plan_output_path_conflict(context: ProcessContext) -> None:
    context.write_plan_control_file(destination=".repo/plans/alpha.json")


def _already_applied(context: ProcessContext) -> None:
    _plan_alpha(context)
    result = context.run(("capability", "apply", ".repo/plans/alpha.json"))
    assert result.returncode == 0, result.stdout + result.stderr


def _bounded_capabilities(context: ProcessContext) -> None:
    context.write_declaration(name="alpha", status="draft")
    context.write_declaration(name="beta", status="active")


CONTROL_PROCESS_CASES = (
    ProcessCase(
        identifier="capabilities-default-json-stable-envelope",
        command="capabilities",
        catalog_command=ControlCommandName.CAPABILITIES,
        args=("capabilities",),
        setup=_no_setup,
        exit_code=0,
        error_code=None,
        assert_document=_assert_empty_capabilities,
    ),
    ProcessCase(
        identifier="status-default-json-with-closed-stdin",
        command="status",
        catalog_command=ControlCommandName.STATUS,
        args=("status",),
        setup=_no_setup,
        exit_code=0,
        error_code=None,
        assert_document=_assert_status_without_prompt,
    ),
    ProcessCase(
        identifier="capability-plan-default-json",
        command="capability plan",
        catalog_command=ControlCommandName.CAPABILITY_PLAN,
        args=(
            "capability",
            "plan",
            "alpha",
            "--inbound",
            "python",
            "--output",
            ".repo/plans/alpha.json",
        ),
        setup=_no_setup,
        exit_code=0,
        error_code=None,
        assert_document=_assert_plan_document,
    ),
    ProcessCase(
        identifier="unknown-command",
        command="cli",
        catalog_command=None,
        args=("unknown-command",),
        setup=_no_setup,
        exit_code=2,
        error_code="invalid_syntax",
        assert_document=_nothing,
    ),
    ProcessCase(
        identifier="invalid-plan-schema",
        command="capability apply",
        catalog_command=ControlCommandName.CAPABILITY_APPLY,
        args=("capability", "apply", ".repo/plans/invalid-schema.json"),
        setup=_invalid_schema,
        exit_code=3,
        error_code="invalid_plan",
        assert_document=_nothing,
    ),
    ProcessCase(
        identifier="stale-plan",
        command="capability apply",
        catalog_command=ControlCommandName.CAPABILITY_APPLY,
        args=("capability", "apply", ".repo/plans/alpha.json"),
        setup=_stale_plan,
        exit_code=3,
        error_code="stale_plan",
        assert_document=_nothing,
    ),
    ProcessCase(
        identifier="plan-output-path-conflict",
        command="capability plan",
        catalog_command=ControlCommandName.CAPABILITY_PLAN,
        args=(
            "capability",
            "plan",
            "alpha",
            "--inbound",
            "python",
            "--output",
            ".repo/plans/alpha.json",
        ),
        setup=_plan_output_path_conflict,
        exit_code=3,
        error_code="plan_output_unavailable",
        assert_document=_nothing,
    ),
    ProcessCase(
        identifier="already-applied",
        command="capability apply",
        catalog_command=ControlCommandName.CAPABILITY_APPLY,
        args=("capability", "apply", ".repo/plans/alpha.json"),
        setup=_already_applied,
        exit_code=0,
        error_code=None,
        assert_document=_assert_already_applied,
    ),
    ProcessCase(
        identifier="capabilities-bounded",
        command="capabilities",
        catalog_command=ControlCommandName.CAPABILITIES,
        args=("capabilities", "--limit", "1"),
        setup=_bounded_capabilities,
        exit_code=0,
        error_code=None,
        assert_document=_assert_bounded_capabilities,
    ),
)


def process_case_command_names() -> frozenset[ControlCommandName]:
    """Return the catalog commands that have at least one detached process case."""
    return frozenset(
        case.catalog_command for case in CONTROL_PROCESS_CASES if case.catalog_command is not None
    )


def _catalog_command_names() -> frozenset[ControlCommandName]:
    return frozenset(ControlCommandName(str(spec.name)) for spec in COMMAND_CATALOG)


def assert_process_cases_cover_control_catalog() -> None:
    """Fail when a public control command lacks detached process evidence."""
    assert process_case_command_names() == _catalog_command_names()


def run_process_case(case: ProcessCase, root: Path) -> subprocess.CompletedProcess[str]:
    """Prepare one isolated repository, then run the case's public command once."""
    context = ProcessContext(root=root)
    case.setup(context)
    return context.run(case.args)
