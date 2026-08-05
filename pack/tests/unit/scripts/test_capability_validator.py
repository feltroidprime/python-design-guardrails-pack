from pathlib import Path
import re
import shutil
import subprocess
import sys

CAPABILITIES = (
    (Path("src/product/billing"), "product.billing"),
    (Path("src/product/reporting"), "product.reporting"),
)
RULES = frozenset({"CAP001", "CAP002", "CAP003"})


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def run_validator(repository: Path, capability: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # ARCH-EXCEPTION: ADR-0007
        [
            sys.executable,
            "-m",
            "scripts.capability_validator",
            "--repository-root",
            str(repository),
            "--root",
            str(capability),
        ],
        cwd=repository_root(),
        capture_output=True,
        text=True,
        check=False,
    )


def seed_capability(repository: Path, root: Path) -> None:
    for relative in (
        Path("api.py"),
        Path("domain/model.py"),
        Path("application/service.py"),
        Path("adapters/inbound/cli.py"),
        Path("adapters/outbound/store.py"),
    ):
        path = repository / root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("", encoding="utf-8")


def resolved_rules(result: subprocess.CompletedProcess[str]) -> frozenset[str]:
    match = re.search(r"rules=([A-Z0-9,]+)", result.stdout)
    assert match is not None, result.stdout + result.stderr
    return frozenset(match.group(1).split(","))


def assert_rejected(result: subprocess.CompletedProcess[str], rule: str) -> None:
    assert result.returncode == 1
    assert rule in result.stderr
    assert resolved_rules(result) == RULES


def test_every_capability_obeys_the_same_structural_contract(tmp_path: Path) -> None:
    """One contract, and no ownership argument. A capability is a directory in the package."""
    for root, _module in CAPABILITIES:
        seed_capability(tmp_path, root)

    baselines = [run_validator(tmp_path, root) for root, _module in CAPABILITIES]
    assert all(result.returncode == 0 for result in baselines)
    assert {resolved_rules(result) for result in baselines} == {RULES}

    for index, (root, module) in enumerate(CAPABILITIES):
        api = tmp_path / root / "api.py"
        api.unlink()
        assert_rejected(run_validator(tmp_path, root), "CAP001")
        _ = api.write_text("", encoding="utf-8")

        domain = tmp_path / root / "domain"
        shutil.rmtree(domain)
        assert_rejected(run_validator(tmp_path, root), "CAP001")
        (domain / "model.py").parent.mkdir(parents=True)
        _ = (domain / "model.py").write_text("", encoding="utf-8")

        domain_model = domain / "model.py"
        _ = domain_model.write_text(
            f"from {module}.application import service\n",
            encoding="utf-8",
        )
        assert_rejected(run_validator(tmp_path, root), "CAP002")
        _ = domain_model.write_text("", encoding="utf-8")

        _ = domain_model.write_text("import third_party_framework\n", encoding="utf-8")
        assert_rejected(run_validator(tmp_path, root), "CAP002")
        _ = domain_model.write_text("", encoding="utf-8")

        consumer = tmp_path / f"consumer_{index}.py"
        _ = consumer.write_text(f"from {module}.domain import model\n", encoding="utf-8")
        assert_rejected(run_validator(tmp_path, root), "CAP003")
        consumer.unlink()
