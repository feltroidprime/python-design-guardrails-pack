"""Group 1: root-to-terminal parity, `PAR-1` to `PAR-11`.

The group states invariants `P1` to `P5`, refusals `R1` to `R9`, the two path
renames, and the offline rule. Every projection here runs from the installed
console script, and the whole group reads `TERM` before any assertion of
another group writes into it.
"""

from collections.abc import Callable
from pathlib import Path
import zipfile

from guardrails_pack.bootstrap.tests.acceptance.code import (
    OFFLINE_PROBE,
    PROBE_MODULE,
    SOCKET_FAILURE,
    Tokens,
    archive_digests,
    commit_digests,
    compare,
    grep,
    pack_tokens,
)
from guardrails_pack.bootstrap.tests.acceptance.conftest import Project, project_once
from guardrails_pack.bootstrap.tests.acceptance.harness import Outcome, release_bytes, run
from guardrails_pack.bootstrap.tests.acceptance.packs import (
    PAYLOAD,
    Pack,
    overlay_release,
)

NOTHING_WAS_WRITTEN = "Nothing was written."
READ_ONLY = 0o500
WRITABLE = 0o700


def token_pattern(tokens: Tokens) -> str:
    """A grep pattern that matches either pack token."""
    return f"{tokens.project}|{tokens.package}"


def test_par_1_the_shipped_payload_equals_the_archive_of_head(
    root: Path, wheel: Path, work: Path
) -> None:
    """`PAR-1`: a wheel never ships a tree that the commit does not have."""
    tokens = pack_tokens(root)
    extracted = work / "payload"
    extracted.mkdir(exist_ok=True)
    with zipfile.ZipFile(wheel) as opened:
        member = opened.extract(f"{tokens.package}/{PAYLOAD}", extracted)

    shipped = archive_digests(Path(member))
    committed = commit_digests(root, work / "head.tar")

    assert dict(shipped) == dict(committed)


def differing(first: dict[str, bytes], second: dict[str, bytes]) -> list[str]:
    """Every key of two surfaces whose bytes or whose presence disagree."""
    return sorted(key for key in first.keys() | second.keys() if first.get(key) != second.get(key))


def test_par_2_the_pack_owned_surface_is_name_blind(term: Project, term2: Project) -> None:
    """`PAR-2`: no file an update rewrites carries the identity of one project.

    The comparison reads release content through git, never the directory. Both
    trees have run their own gate by now, and a bytecode cache is neither
    pack-owned nor part of any release.
    """
    surface = differing(
        release_bytes(term.path, "pack"),
        release_bytes(term2.path, "pack"),
    )
    foundation = differing(
        release_bytes(term.path, f"src/{term.tokens.package}/_foundation"),
        release_bytes(term2.path, f"src/{term2.tokens.package}/_foundation"),
    )
    marker = (term.path / "src" / term.tokens.package / "py.typed").read_bytes()

    assert surface == []
    assert foundation == []
    assert marker == (term2.path / "src" / term2.tokens.package / "py.typed").read_bytes()


def test_par_3_no_pack_token_under_the_pack_directory(term: Project, toolenv: Pack) -> None:
    """`PAR-3`: the surface an update rewrites holds no pack token."""
    found = grep(term.path / "pack", token_pattern(toolenv.tokens))

    assert found == ()


def test_par_4_no_pack_token_anywhere(term: Project, toolenv: Pack) -> None:
    """`PAR-4`: invariant `P2`, which refusal `R7` reads inside the projection."""
    found = grep(term.path, token_pattern(toolenv.tokens))

    assert found == ()


def test_par_5_the_path_sets_agree_after_the_rename(
    root: Path, term: Project, toolenv: Pack
) -> None:
    """`PAR-5`: the projection drops no file and adds none."""
    measured = compare(root, term.path, toolenv.tokens, term.tokens)

    assert (measured.missing, measured.added) == (frozenset(), frozenset())


def test_par_6_every_file_is_byte_identical(root: Path, term: Project, toolenv: Pack) -> None:
    """`PAR-6`: invariant `P1`, so no file receives an edit beyond the token swap."""
    measured = compare(root, term.path, toolenv.tokens, term.tokens)

    assert measured.changed == frozenset()


def test_par_7_every_starting_file_shadows_a_file(root: Path, term: Project, toolenv: Pack) -> None:
    """`PAR-7`: invariant `P4`, measured over the tree after the rename."""
    measured = compare(root, term.path, toolenv.tokens, term.tokens)

    assert measured.unshadowed == frozenset()


def test_par_8_every_starting_file_landed_and_differs(
    root: Path, term: Project, toolenv: Pack
) -> None:
    """`PAR-8`: an overlay that replaced nothing would be silent without this."""
    measured = compare(root, term.path, toolenv.tokens, term.tokens)

    assert measured.untouched_overlay == frozenset()


def test_par_9_every_path_component_of_a_pack_token_is_renamed(
    term: Project, toolenv: Pack
) -> None:
    """`PAR-9`: correction `C3`, which the prototype hit on its first run."""
    found = run(
        (
            "find",
            str(term.path),
            "-name",
            ".git",
            "-prune",
            "-o",
            "-name",
            toolenv.tokens.package,
            "-o",
            "-name",
            toolenv.tokens.project,
            "-print",
        ),
        term.path,
    )

    assert found.out.strip() == ""


def test_par_10_the_projection_opens_no_socket(toolenv: Pack, work: Path) -> None:
    """`PAR-10`: Code D, so the projection is testable and private offline."""
    probe = work / "nonet"
    probe.mkdir(exist_ok=True)
    _ = (probe / PROBE_MODULE).write_text(OFFLINE_PROBE, encoding="utf-8")

    made = project_once(toolenv.script, "net-probe", work / "netterm", PYTHONPATH=str(probe))

    assert SOCKET_FAILURE not in made.outcome.text
    assert (made.path / "pyproject.toml").is_file(), made.outcome.text


def refusal(outcome: Outcome, rule: str) -> bool:
    """One refusal names its rule, ends with the promise, and exits non-zero."""
    message = outcome.text.strip()
    return outcome.code != 0 and f"{rule}: " in message and NOTHING_WAS_WRITTEN in message


def test_par_11_the_six_refusals_before_any_write(toolenv: Pack, work: Path) -> None:
    """`PAR-11`, `R1` to `R6`: every rule that answers before the destination exists."""
    stage = work / "refuse"
    stage.mkdir(exist_ok=True)
    existing = stage / "taken"
    existing.mkdir(exist_ok=True)
    locked = stage / "locked"
    locked.mkdir(exist_ok=True)
    locked.chmod(READ_ONLY)
    cases: tuple[tuple[str, Callable[[], Project]], ...] = (
        ("R1", lambda: project_once(toolenv.script, "bad name", stage / "one")),
        ("R3", lambda: project_once(toolenv.script, "json", stage / "three")),
        ("R4", lambda: project_once(toolenv.script, toolenv.tokens.project, stage / "four")),
        ("R5", lambda: project_once(toolenv.script, "taken-name", existing)),
        ("R6", lambda: project_once(toolenv.script, "locked-name", locked / "child")),
    )
    try:
        refused = {rule: build() for rule, build in cases}
    finally:
        locked.chmod(WRITABLE)

    assert [rule for rule, made in refused.items() if not refusal(made.outcome, rule)] == []
    assert [rule for rule, made in refused.items() if made.path.exists()] == ["R5"]


def test_par_11_r2_refuses_an_invalid_import_package(toolenv: Pack, work: Path) -> None:
    """`PAR-11`, `R2`: the derived import name must be a valid Python identifier."""
    made = project_once(toolenv.script, "good-name", work / "r2", package="Bad")

    assert refusal(made.outcome, "R2")
    assert not made.path.exists()


def test_par_11_r7_refuses_a_surviving_pack_token(toolenv: Pack, work: Path) -> None:
    """`PAR-11`, `R7`: a name that holds a pack token leaves that token behind."""
    made = project_once(toolenv.script, f"my-{toolenv.tokens.project}-thing", work / "r7")

    assert refusal(made.outcome, "R7")
    assert not made.path.exists()


def test_par_11_r8_refuses_a_surviving_capability_directory(toolenv: Pack, work: Path) -> None:
    """`PAR-11`, `R8`: a package named after the capability leaves its name on disk."""
    made = project_once(toolenv.script, "boot-thing", work / "r8", package="bootstrap")

    assert refusal(made.outcome, "R8")
    assert not made.path.exists()


def test_par_11_r9_refuses_a_starting_file_that_shadows_nothing(root: Path, work: Path) -> None:
    """`PAR-11`, `R9`: the overlay can only replace a file, never add one."""
    broken = overlay_release(root, work)

    made = project_once(broken.script, "overlay-thing", work / "r9")

    assert refusal(made.outcome, "R9")
    assert not made.path.exists()
