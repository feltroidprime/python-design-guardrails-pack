"""Black-box tests for property selection and bounded CrossHair invocation."""

import json
import os
from pathlib import Path
import subprocess
import sys

from tests.test_proof_guard import POLICY_TOML, PROOF_TOML

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_SCRIPTS = REPO_ROOT / "pack" / "scripts"

STATEFUL_PROOF_TOML = """
schema_version = 1

[[properties]]
id = "DEMO-REPLAY-SAFE"
title = "Retries remain safe"
statement = "Retries never duplicate an effect."
scope = "One sequential workflow run."
assumptions = []
kind = "state_machine"
strength = "normative"
targets = ["demo.application.use_cases:Handler.__call__"]
oracles = ["demo.application.specifications:replay_is_safe"]
evidence = ["hypothesis-stateful", "falsifier"]
counterexample = "One retry duplicates an effect."
failure_modes = ["duplicate effect"]
"""


def crosshair_project(tmp_path: Path, manifest: str) -> Path:
    """A project shaped like the real tree: guard scripts and proof under `pack/`."""
    root = tmp_path / "crosshair-project"
    scripts = root / "pack" / "scripts"
    scripts.mkdir(parents=True)
    (root / "src" / "demo").mkdir(parents=True)
    (scripts / "__init__.py").write_text("", encoding="utf-8")
    for name in (
        "architecture_policy.py",
        "crosshair_gate.py",
        "identity.py",
        "proof_catalog.py",
        "proof_catalog_model.py",
        "proof_catalog_schema.py",
    ):
        (scripts / name).write_text(
            (PACK_SCRIPTS / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    proof_root = root / "pack" / "proof"
    proof_root.mkdir()
    (proof_root / "policy.toml").write_text(POLICY_TOML, encoding="utf-8")
    (proof_root / "foundation.toml").write_text(manifest, encoding="utf-8")
    return root


def run_gate(
    root: Path,
    *arguments: str,
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(root / "pack")
    if extra_environment is not None:
        environment.update(extra_environment)
    return subprocess.run(
        [sys.executable, "-m", "scripts.crosshair_gate", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def test_property_without_symbolic_targets_is_a_fast_noop(tmp_path: Path) -> None:
    root = crosshair_project(tmp_path, STATEFUL_PROOF_TOML)

    completed = run_gate(root, "fast", "DEMO-REPLAY-SAFE")

    assert completed.returncode == 0
    assert "no explicit targets for DEMO-REPLAY-SAFE" in completed.stdout


def test_unknown_property_id_fails_before_crosshair_execution(tmp_path: Path) -> None:
    root = crosshair_project(tmp_path, PROOF_TOML)

    completed = run_gate(root, "fast", "UNKNOWN-PROPERTY")

    assert completed.returncode == 2
    assert "Unknown property ID(s): UNKNOWN-PROPERTY" in completed.stderr


FAKE_CROSSHAIR = """\
import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
record = Path(os.environ["CROSSHAIR_ARGUMENTS"])
calls = json.loads(record.read_text(encoding="utf-8")) if record.exists() else []
calls.append(arguments)
record.write_text(json.dumps(calls), encoding="utf-8")
if source_record := os.environ.get("CROSSHAIR_SOURCE_PATHS"):
    source_path = Path(source_record)
    values = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else []
    values.append(os.environ["PYTHONPATH"].split(os.pathsep))
    source_path.write_text(json.dumps(values), encoding="utf-8")
if "symbolic_canary" in arguments[-1] and os.environ.get("CROSSHAIR_REFUTE_CANARY") == "1":
    print(f"canary.py:1: error: \\"def denies()\\" yields false")
    sys.exit(1)
"""

FAST_BUDGET_ARGUMENTS = [
    "check",
    "--report_all",
    "--analysis_kind=icontract",
    "--max_uninteresting_iterations=4",
    "--per_path_timeout=0.25",
    "--per_condition_timeout=1.5",
]
CI_BUDGET_ARGUMENTS = [
    "check",
    "--report_all",
    "--analysis_kind=icontract",
    "--max_uninteresting_iterations=12",
    "--per_path_timeout=0.75",
    "--per_condition_timeout=4.0",
]
CANARY_BUDGET_ARGUMENTS = [
    "check",
    "--report_all",
    "--analysis_kind=icontract",
    "--max_uninteresting_iterations=16",
    "--per_path_timeout=1.5",
    "--per_condition_timeout=8.0",
]


def stub_crosshair(root: Path) -> Path:
    crosshair = root / "crosshair"
    crosshair.mkdir()
    (crosshair / "__init__.py").write_text("", encoding="utf-8")
    (crosshair / "__main__.py").write_text(FAKE_CROSSHAIR, encoding="utf-8")
    return root / "crosshair-arguments.json"


def test_gate_analyses_each_target_and_the_canary_with_the_fast_budget(
    tmp_path: Path,
) -> None:
    root = crosshair_project(tmp_path, PROOF_TOML)
    arguments_path = stub_crosshair(root)

    completed = run_gate(
        root,
        "fast",
        "DEMO-PRESERVES-VALUE",
        extra_environment={
            "CROSSHAIR_ARGUMENTS": str(arguments_path),
            "CROSSHAIR_REFUTE_CANARY": "1",
        },
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(arguments_path.read_text(encoding="utf-8")) == [
        [*FAST_BUDGET_ARGUMENTS, "demo.feature.domain.decisions.identity"],
        [*CANARY_BUDGET_ARGUMENTS, "verification.harness.symbolic_canary.refutable_echo"],
    ]
    assert "DEMO-PRESERVES-VALUE | demo.feature.domain.decisions:identity" in completed.stdout
    assert "SYMBOLIC-CANARY" in completed.stdout


def test_ci_canary_keeps_the_symbolic_minimum_budget(tmp_path: Path) -> None:
    root = crosshair_project(tmp_path, PROOF_TOML)
    arguments_path = stub_crosshair(root)

    completed = run_gate(
        root,
        "ci",
        "DEMO-PRESERVES-VALUE",
        extra_environment={
            "CROSSHAIR_ARGUMENTS": str(arguments_path),
            "CROSSHAIR_REFUTE_CANARY": "1",
        },
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(arguments_path.read_text(encoding="utf-8")) == [
        [*CI_BUDGET_ARGUMENTS, "demo.feature.domain.decisions.identity"],
        [*CANARY_BUDGET_ARGUMENTS, "verification.harness.symbolic_canary.refutable_echo"],
    ]


def test_gate_builds_pythonpath_from_policy_source_roots(tmp_path: Path) -> None:
    manifest = PROOF_TOML.replace("demo.domain", "pack.demo")
    root = crosshair_project(tmp_path, manifest)
    policy = root / "pack/proof/policy.toml"
    policy.write_text(
        POLICY_TOML.replace('source_roots = ["src", "."]', 'source_roots = ["control", "."]'),
        encoding="utf-8",
    )
    arguments_path = stub_crosshair(root)
    source_paths = root / "crosshair-source-paths.json"

    completed = run_gate(
        root,
        "fast",
        "DEMO-PRESERVES-VALUE",
        extra_environment={
            "CROSSHAIR_ARGUMENTS": str(arguments_path),
            "CROSSHAIR_REFUTE_CANARY": "1",
            "CROSSHAIR_SOURCE_PATHS": str(source_paths),
        },
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    recorded = json.loads(source_paths.read_text(encoding="utf-8"))
    expected = [str(root / "control"), str(root)]
    assert all(paths[:2] == expected for paths in recorded)


def test_unrefuted_symbolic_canary_fails_the_gate(tmp_path: Path) -> None:
    root = crosshair_project(tmp_path, PROOF_TOML)
    arguments_path = stub_crosshair(root)

    completed = run_gate(
        root,
        "fast",
        "DEMO-PRESERVES-VALUE",
        extra_environment={"CROSSHAIR_ARGUMENTS": str(arguments_path)},
    )

    assert completed.returncode == 1
    assert "NOT refuted" in completed.stdout
    assert "PROPERTY[SYMBOLIC-CANARY]" in completed.stderr
    assert "CrossHair proved nothing about the real targets" in completed.stderr


def test_reported_counterexample_names_the_owning_property(tmp_path: Path) -> None:
    root = crosshair_project(tmp_path, PROOF_TOML)
    crosshair = root / "crosshair"
    crosshair.mkdir()
    (crosshair / "__init__.py").write_text("", encoding="utf-8")
    (crosshair / "__main__.py").write_text(
        'import sys\n\nprint("decisions.py:1: error: yields false")\nsys.exit(1)\n',
        encoding="utf-8",
    )

    completed = run_gate(root, "fast", "DEMO-PRESERVES-VALUE")

    assert completed.returncode == 1
    assert (
        "PROPERTY[DEMO-PRESERVES-VALUE] demo.feature.domain.decisions:identity" in completed.stderr
    )
