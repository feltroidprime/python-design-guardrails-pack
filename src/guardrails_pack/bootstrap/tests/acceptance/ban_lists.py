"""The two ban lists of the legacy scan, the legacy paths, and the exemptions.

List 1 holds identifiers and paths. It scans the whole tree, case-sensitive,
and it includes `--cov`, `pytest-cov` and `[tool.coverage`, so a scan of it also
proves that the line-coverage floor is gone. List 2 holds prose. It scans
Markdown and Python files only, case-insensitive. `prose_pattern` builds list 2
from the `_Avoid_` terms of `CONTEXT.md` at scan time, plus `EXTRA_PROSE_TERMS`
below. The vocabulary of the target and the list of retired words therefore
stay one fact in one place.

This module and `CONTEXT.md` state the banned words, so `SOURCE_FILES` exempts
both of them from their own scan.

List 1 omits two identifiers on purpose: `schema_version`, the first key of
every proof catalog and of the machine envelope, and `proof_catalog`, the name
of three surviving modules of `pack/scripts/`. Both name live code that the
deletion boundary keeps, so a ban on either flags a survivor, not a deletion.
This paragraph is the record of that decision.

Two trees are exempt in both the Root Pack and a Terminal Project, because this
repository owns neither their words nor their files: `docs/vendored/`, a
read-only third-party documentation pin, and `.agents/`, which holds agent
skills from an external source when a checkout installs them. The exemption
stands whether or not that tree is present. The gate itself excludes the same
two trees. One more exemption applies to the Root Pack only:
`CHANGELOG.md`, which records the pack's own history. A Terminal Project takes
a fresh `CHANGELOG.md` from `initial/`, so it needs no exemption of its own.
"""

from pathlib import Path

__all__ = [
    "AVOID_PREFIX",
    "EXEMPT_IN_PACK",
    "EXTRA_PROSE_TERMS",
    "GENERATED_DIRECTORY",
    "IDENTIFIER_PATTERN",
    "LEGACY_PATHS",
    "PROSE_SUFFIXES",
    "SOURCE_FILES",
    "UNOWNED_TREES",
    "UNSEARCHABLE_TERMS",
    "VOCABULARY_FILE",
    "avoid_terms",
    "exempt",
    "prose_pattern",
]

IDENTIFIER_PATTERN = (
    r"repoctl|copier|\.jinja|instantiate\.py|_generated|ownership_zone|ownership_policy"
    r"|ownership_guard|capability_validator|quality_gate\.py"
    r"|\bOWN00[1-5]\b|\bARCH02[45]\b|\bARCH031\b|\bCAP00[1-3]\b|\bN[012]\b"
    r"|pytest-cov|--cov|\[tool\.coverage"
)
# List 2 reads prose, and these are the two kinds of file that carry it. The
# scan reads a file list rather than a directory, so each entry is a file name
# ending and never a shell pattern.
PROSE_SUFFIXES = (".md", ".py")
# The document that states the vocabulary of the target, and with it the words
# the target retired. It is the source of list 2.
VOCABULARY_FILE = "CONTEXT.md"
AVOID_PREFIX = "_Avoid_:"
# Two terms that name deleted machinery and that `CONTEXT.md` does not carry,
# because no surviving term replaces either one.
EXTRA_PROSE_TERMS = ("lifecycle state", "declaration file")
# Four `_Avoid_` terms that no word search can carry, and the reason for each.
# Each of the first three tells a writer which word not to use for one named
# concept, and each is an ordinary word for another concept in the same
# documents.
#
# * `generator` is also the name of a standard-library type.
# * `user code` and `capability code` are the correct words for the User-owned
#   Surface. `CONTEXT.md` retires them for one other concept, the Pack-owned
#   Surface, and a word search cannot make that judgment.
#
# `n0` is absent from list 2 for a different reason: list 1 already carries it,
# case-sensitive and over the whole tree rather than over prose alone.
UNSEARCHABLE_TERMS = frozenset({"generator", "user code", "capability code", "n0"})
# The subsystems of a deleted architecture, which must exist on disk in neither
# tree. They sit beside the two lists because each name is also a banned
# identifier.
LEGACY_PATHS = (
    "template",
    "copier.yml",
    "instantiate.py",
    "scripts/quality_gate.py",
    ".repo",
    "proof/modules",
    "tests/modules",
    "verification/modules",
    "docs/product",
)
GENERATED_DIRECTORY = "_generated"
# The two files that state the banned words, so a scan of either always finds
# them.
SOURCE_FILES = ("ban_lists.py", VOCABULARY_FILE)
# Two trees whose words this repository does not own, in either project.
UNOWNED_TREES = ("docs/vendored", ".agents")
# The Root Pack keeps its own history. A Terminal Project starts a fresh one.
EXEMPT_IN_PACK = ("CHANGELOG.md",)


def exempt(line: str, *names: str) -> bool:
    """Whether one grep line names a file that a list exempts.

    A grep line is `path:number:content`, and the path is relative to the tree
    under scan. Only the path decides an exemption, because a document that
    names an exempt file must not exempt itself. Every word search of the
    acceptance suite reads this one rule, so no scan can carry an exemption of
    its own.
    """
    path = line.split(":", 1)[0]
    return any(name in path for name in names)


def avoid_terms(tree: Path) -> tuple[str, ...]:
    """Every `_Avoid_` term that `CONTEXT.md` of *tree* states, in lower case."""
    document = (tree / VOCABULARY_FILE).read_text(encoding="utf-8")
    found: list[str] = []
    for line in document.splitlines():
        if not line.startswith(AVOID_PREFIX):
            continue
        for term in line.removeprefix(AVOID_PREFIX).split(","):
            cleaned = term.strip().lower()
            if cleaned and cleaned not in found:
                found.append(cleaned)
    return tuple(found)


def prose_pattern(tree: Path) -> str:
    """List 2 of Code B: the retired prose of *tree* that a search can carry."""
    searchable = [term for term in avoid_terms(tree) if term not in UNSEARCHABLE_TERMS]
    searchable.extend(term for term in EXTRA_PROSE_TERMS if term not in searchable)
    return "|".join(searchable)
