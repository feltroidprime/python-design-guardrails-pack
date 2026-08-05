from pathlib import Path
import subprocess
import sys

from scripts.quality_gate import checks


def generated_repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # ARCH-EXCEPTION: ADR-0007
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def architecture(product_root: str = "product") -> str:
    return f"""\
[ownership.roots]
FOUNDATION = ["architecture.toml", "foundation"]
PRODUCT = ["{product_root}"]
DERIVED = ["derived"]
DECLARATION = ["declaration"]
"""


def seed_repository(root: Path) -> None:
    _ = (root / "architecture.toml").write_text(architecture(), encoding="utf-8")
    for path in (
        root / "foundation/base.txt",
        root / "product/user.txt",
        root / "derived/index.json",
        root / "declaration/repository.toml",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(f"{path.name}\n", encoding="utf-8")
    initialized = run(["git", "init", "--quiet", "--initial-branch=main"], root)
    assert initialized.returncode == 0, initialized.stderr
    staged = run(["git", "add", "--all"], root)
    assert staged.returncode == 0, staged.stderr


def run_guard(repository: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            "-m",
            "scripts.ownership_guard",
            "--root",
            str(repository),
        ],
        generated_repository_root(),
    )


def test_guard_enforces_disjoint_and_complete_repository_ownership(tmp_path: Path) -> None:
    seed_repository(tmp_path)

    complete = run_guard(tmp_path)
    assert complete.returncode == 0, complete.stdout + complete.stderr
    assert "classified 5 repository paths" in complete.stdout

    _ = (tmp_path / "architecture.toml").write_text(
        architecture("foundation/product"),
        encoding="utf-8",
    )
    overlapping = run_guard(tmp_path)
    assert overlapping.returncode == 1
    assert "FOUNDATION:foundation" in overlapping.stderr
    assert "PRODUCT:foundation/product" in overlapping.stderr

    _ = (tmp_path / "architecture.toml").write_text(
        architecture().replace("DECLARATION =", "STATE ="),
        encoding="utf-8",
    )
    wrong_zones = run_guard(tmp_path)
    assert wrong_zones.returncode == 1
    assert "OWN005" in wrong_zones.stderr
    assert "DECLARATION" in wrong_zones.stderr
    assert "STATE" in wrong_zones.stderr

    _ = (tmp_path / "architecture.toml").write_text(architecture(), encoding="utf-8")
    _ = (tmp_path / "outside.txt").write_text("unowned\n", encoding="utf-8")
    staged = run(["git", "add", "outside.txt"], tmp_path)
    assert staged.returncode == 0, staged.stderr
    unclassified = run_guard(tmp_path)
    assert unclassified.returncode == 1
    assert "outside.txt" in unclassified.stderr

    assert (sys.executable, "-m", "scripts.ownership_guard") in {
        check.command for check in checks()
    }
