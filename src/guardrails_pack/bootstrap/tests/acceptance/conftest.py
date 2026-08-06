"""The seven fixture trees of the acceptance suite, and the one marker it carries.

| Name | What it is |
|---|---|
| `ROOT` | the Root Pack checkout, clean, at `HEAD` |
| `WHEEL` | the wheel built from `ROOT` at `HEAD` |
| `TOOLENV` | a throwaway tool installation of `WHEEL`; its script is `pyrepo` |
| `TERM` | `my-product`, projected by `TOOLENV` into an empty directory |
| `TERM2` | `other-thing`, projected the same way |
| `OLD` | a Terminal Project projected from the previous released pack |
| `DEFECT` | a copy of `TERM` with exactly one injected defect, one per case |

Every fixture below builds one of them. `pytest_collection_modifyitems` marks
every item of this package `acceptance`, so rule `H3` cannot be lost by a
forgotten marker in one module.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from guardrails_pack.bootstrap.tests.acceptance.code import CAPABILITY, Tokens, pack_tokens
from guardrails_pack.bootstrap.tests.acceptance.harness import (
    Outcome,
    copy_tree,
    git,
    make_repository,
    porcelain,
    run,
    sync,
)
from guardrails_pack.bootstrap.tests.acceptance.packs import (
    Pack,
    build_wheel,
    install_tool,
    previous_release,
)

MARKER = "acceptance"
SEPARATORS = ("-", ".")
PROJECT_NAME = "my-product"
SECOND_NAME = "other-thing"
OLD_NAME = "aged-thing"
SUITE_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class Project:
    """One projected Terminal Project: where it landed, its identity, its outcome."""

    path: Path
    tokens: Tokens
    outcome: Outcome


def derived_package(name: str) -> str:
    """The import package that a distribution name gives, by separator swap."""
    derived = name
    for separator in SEPARATORS:
        derived = derived.replace(separator, "_")
    return derived


def project_once(
    script: Path, name: str, destination: Path, *, package: str = "", **overrides: str
) -> Project:
    """Run one `init` from the installed console script, and report the result.

    *package* becomes the `--package` option, and every other keyword becomes an
    environment variable of the command, which is how the offline probe of
    `PAR-10` reaches the projection.
    """
    option = ("--package", package) if package else ()
    outcome = run(
        (str(script), CAPABILITY, "init", name, str(destination), *option),
        destination.parent,
        **overrides,
    )
    return Project(
        path=destination,
        tokens=Tokens(project=name, package=package or derived_package(name)),
        outcome=outcome,
    )


def complete(made: Project) -> Project:
    """Finish the two steps that a red gate cut short, and change nothing else.

    `init` runs `git init`, `just setup`, then the first commit, and `just setup`
    ends with the gate. While any hook of the gate is red the recipe fails, so
    `init` stops before the commit and reports exit 4. Every assertion of this
    suite that reads `git ls-files --cached` would then measure the gate rather
    than the property it names.

    This function commits such a tree, and it does nothing at all to a tree that
    `init` already committed. Assertion `LEG-5` states the gate outcome itself,
    so a red hook stays visible where it belongs.
    """
    if git(made.path, "rev-parse", "HEAD").code == 0:
        return made
    _ = sync(made.path)
    _ = make_repository(made.path, f"Initial commit of {made.tokens.project}")
    return made


@pytest.fixture(scope="session")
def work(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One throwaway directory for every tree, wheel and tool of the session."""
    return tmp_path_factory.mktemp(MARKER)


@pytest.fixture(scope="session")
def root() -> Path:
    """`ROOT`: the checkout, which rule `H2` requires to be committed."""
    checkout = SUITE_ROOT.parents[4]
    dirty = porcelain(checkout)
    assert not dirty, f"H2 needs a committed tree. Uncommitted: {dirty}"
    return checkout


@pytest.fixture(scope="session")
def wheel(root: Path, work: Path) -> Path:
    """`WHEEL`: one wheel of `HEAD`, with the projection payload inside it."""
    return build_wheel(root, work / "dist")


@pytest.fixture(scope="session")
def toolenv(root: Path, wheel: Path, work: Path) -> Pack:
    """`TOOLENV`: the installed console script that every projection runs from."""
    return Pack(
        root=root,
        wheel=wheel,
        script=install_tool(wheel, work, "current"),
        tokens=pack_tokens(root),
    )


@pytest.fixture(scope="session")
def term(toolenv: Pack, work: Path) -> Project:
    """`TERM`: `my-product`, projected by the installed console script."""
    return complete(project_once(toolenv.script, PROJECT_NAME, work / "term"))


@pytest.fixture(scope="session")
def term2(toolenv: Pack, work: Path) -> Project:
    """`TERM2`: `other-thing`, projected the same way, for every name-blind check."""
    return complete(project_once(toolenv.script, SECOND_NAME, work / "term2"))


@pytest.fixture(scope="session")
def previous(root: Path, work: Path) -> Pack:
    """The release that `OLD` is born from, one version before the current tree."""
    return previous_release(root, work)


@pytest.fixture(scope="session")
def aged(previous: Pack, work: Path) -> Project:
    """`OLD`: one Terminal Project of the previous release, kept pristine."""
    return complete(project_once(previous.script, OLD_NAME, work / "old"))


@pytest.fixture
def old(aged: Project, tmp_path: Path) -> Project:
    """One fresh committed copy of `OLD`, because every update writes to it."""
    copy = copy_tree(aged.path, tmp_path / "old")
    _ = sync(copy)
    _ = make_repository(copy, "The project as its release left it")
    return Project(path=copy, tokens=aged.tokens, outcome=aged.outcome)


@pytest.fixture
def defect(term: Project, tmp_path: Path) -> Iterator[Callable[[str], Path]]:
    """A factory of `DEFECT` trees: one copy of `TERM` per injected defect."""
    made: list[Path] = []

    def build(name: str) -> Path:
        copy = copy_tree(term.path, tmp_path / name)
        _ = sync(copy)
        _ = make_repository(copy, f"The project before the {name} defect")
        made.append(copy)
        return copy

    yield build
    made.clear()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every assertion of this package `acceptance` (rule `H3`)."""
    for item in items:
        if SUITE_ROOT in Path(str(item.path)).parents:
            item.add_marker(MARKER)
