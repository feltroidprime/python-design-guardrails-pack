"""Black-box tests for property selection and bounded CrossHair invocation."""

import json
import os
from pathlib import Path
import subprocess
import sys

from tests.test_proof_guard import PROOF_TOML

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = REPO_ROOT / "template" / "scripts"

STATEFUL_PROOF_TOML = '''
schema_version = 1

[policy]
source_root = "src"
test_root = "verification/tests"
behavior_roots = ["demo.domain"]
excluded_module_stems = ["__init__", "specifications"]
oracle_module_stems = ["specifications"]

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
'''


def crosshair_project(tmp_path: Path, manifest: str) -> Path:
    root = tmp_path / "crosshair-project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "__init__.py").write_text("", encoding="utf-8")
    for name in ("crosshair_gate.py", "proof_catalog.py"):
        (scripts / name).write_text(
            (TEMPLATE_SCRIPTS / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (root / "proof.toml").write_text(manifest, encoding="utf-8")
    return root


def run_gate(
    root: Path,
    *arguments: str,
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(root)
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


def test_gate_invokes_crosshair_module_with_exact_target_and_fast_budget(
    tmp_path: Path,
) -> None:
    root = crosshair_project(tmp_path, PROOF_TOML)
    crosshair = root / "crosshair"
    crosshair.mkdir()
    (crosshair / "__init__.py").write_text("", encoding="utf-8")
    arguments_path = root / "crosshair-arguments.json"
    (crosshair / "__main__.py").write_text(
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        "import sys\n\n"
        "Path(os.environ['CROSSHAIR_ARGUMENTS']).write_text(\n"
        "    json.dumps(sys.argv[1:]),\n"
        "    encoding='utf-8',\n"
        ")\n",
        encoding="utf-8",
    )

    completed = run_gate(
        root,
        "fast",
        "DEMO-PRESERVES-VALUE",
        extra_environment={"CROSSHAIR_ARGUMENTS": str(arguments_path)},
    )

    assert completed.returncode == 0
    assert json.loads(arguments_path.read_text(encoding="utf-8")) == [
        "check",
        "--analysis_kind=icontract",
        "--max_uninteresting_iterations=4",
        "--per_path_timeout=0.25",
        "--per_condition_timeout=1.5",
        "demo.domain.decisions.identity",
    ]
