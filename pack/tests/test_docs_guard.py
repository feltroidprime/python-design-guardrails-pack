"""Tests for the documentation guard (DOC001-DOC007).

Each test proves that one rule fires on a planted violation and stays silent
on legitimate prose. They go through docs_guard.check_documentation so the
composition under test is the shipped one: one markdown walk, all rule
families. The last test runs the guard over this repository's own
documentation.
"""

from pathlib import Path

from scripts.architecture_policy import load_policy
from scripts.docs_guard import check_documentation

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "pack"

MINIMAL_MAP = (
    "# Documentation map\n\n"
    "| Document | Read it when | Freshness |\n"
    "|---|---|---|\n"
    "| [docs/adr/](adr/) | decisions | dated |\n"
)


def make_repo(tmp_path: Path) -> Path:
    """A minimal repository the guard accepts: manifest, map, ADR template."""
    manifest = (PACK / "architecture.toml").read_text(encoding="utf-8")
    (tmp_path / "architecture.toml").write_text(
        manifest.replace("guardrails_pack", "pkg"), encoding="utf-8"
    )
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    form = (REPO_ROOT / "docs" / "adr" / "0000-template.md").read_text(encoding="utf-8")
    (adr_dir / "0000-template.md").write_text(form, encoding="utf-8")
    (tmp_path / "docs" / "README.md").write_text(MINIMAL_MAP, encoding="utf-8")
    return tmp_path


def write_adr(root: Path, name: str, *, number: str, status: str = "accepted") -> None:
    (root / "docs" / "adr" / name).write_text(
        f"# ADR-{number}: Planted decision\n\n"
        f"- Status: {status}\n"
        "- Date: 2026-07-13\n"
        "- Owners: tests\n"
        "- Revisit trigger: never\n",
        encoding="utf-8",
    )


def add_doc(root: Path, name: str, body: str, *, registered: bool = True) -> None:
    """Create docs/<name> and (by default) claim its row in the map."""
    (root / "docs" / name).write_text(body, encoding="utf-8")
    if registered:
        map_path = root / "docs" / "README.md"
        row = f"| [{name}]({name}) | tests | checked |\n"
        map_path.write_text(map_path.read_text(encoding="utf-8") + row, encoding="utf-8")


def run_guard(root: Path) -> list[str]:
    return [item.code for item in check_documentation(load_policy(root))]


def test_minimal_repository_passes(tmp_path: Path) -> None:
    assert run_guard(make_repo(tmp_path)) == []


def test_doc001_fires_on_broken_inline_code_path(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    add_doc(root, "guide.md", "See `src/pkg/missing/module.py` for details.\n")
    assert run_guard(root) == ["DOC001"]


def test_doc001_fires_on_broken_markdown_link(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    add_doc(root, "guide.md", "See [the gone file](gone.md).\n")
    assert run_guard(root) == ["DOC001"]


def test_doc001_resolves_paths_from_the_package_root(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    module = root / "src" / "pkg" / "domain" / "entities.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    add_doc(root, "guide.md", "Imitate `domain/entities.py`.\n")
    assert run_guard(root) == []


def test_doc001_ignores_fenced_code_blocks_and_urls(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    add_doc(
        root,
        "guide.md",
        "See [uv](https://docs.astral.sh/uv/).\n\n```bash\ncat gone/file.py\n```\n",
    )
    assert run_guard(root) == []


def test_doc002_fires_on_marker_referencing_missing_adr(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    module = root / "src" / "pkg" / "domain" / "entities.py"
    module.parent.mkdir(parents=True)
    module.write_text("location = None  # ARCH-EXCEPTION: ADR-0042\n", encoding="utf-8")
    assert run_guard(root) == ["DOC002"]


def test_doc002_accepts_marker_referencing_existing_adr(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_adr(root, "0001-planted-decision.md", number="0001")
    module = root / "src" / "pkg" / "domain" / "entities.py"
    module.parent.mkdir(parents=True)
    module.write_text("location = None  # ARCH-EXCEPTION: ADR-0001\n", encoding="utf-8")
    assert run_guard(root) == []


def test_doc003_fires_on_bad_adr_file_name(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_adr(root, "my-decision.md", number="0001")
    assert run_guard(root) == ["DOC003"]


def test_doc004_fires_on_heading_not_matching_file_number(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_adr(root, "0001-planted-decision.md", number="0007")
    assert run_guard(root) == ["DOC004"]


def test_doc005_fires_on_missing_front_matter_key(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "docs" / "adr" / "0001-planted-decision.md").write_text(
        "# ADR-0001: Planted decision\n\n- Status: accepted\n- Date: 2026-07-13\n",
        encoding="utf-8",
    )
    assert sorted(run_guard(root)) == ["DOC005", "DOC005"]


def test_doc005_fires_on_unknown_status(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_adr(root, "0001-planted-decision.md", number="0001", status="maybe")
    assert run_guard(root) == ["DOC005"]


def test_doc006_fires_on_numbering_gap(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_adr(root, "0002-planted-decision.md", number="0002")
    assert run_guard(root) == ["DOC006"]


def test_doc006_fires_on_duplicate_number(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_adr(root, "0001-planted-decision.md", number="0001")
    write_adr(root, "0001-second-decision.md", number="0001")
    assert run_guard(root) == ["DOC006"]


def test_doc007_fires_on_unregistered_document(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    add_doc(root, "orphan.md", "No row claims this file.\n", registered=False)
    assert run_guard(root) == ["DOC007"]


def test_doc007_directory_row_covers_contained_documents(tmp_path: Path) -> None:
    # The baseline map registers docs/adr/ as a directory; a second ADR needs no row.
    root = make_repo(tmp_path)
    write_adr(root, "0001-planted-decision.md", number="0001")
    assert run_guard(root) == []


def test_doc007_fires_when_the_map_is_missing(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "docs" / "README.md").unlink()
    assert run_guard(root) == ["DOC007"]


def test_this_repository_satisfies_its_own_documentation_contract() -> None:
    findings = check_documentation(load_policy(REPO_ROOT))
    assert [item.render(REPO_ROOT) for item in findings] == []
