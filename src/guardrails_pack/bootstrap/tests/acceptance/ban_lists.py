"""The two ban lists of Code B of #81, the legacy paths, and the exemptions.

This module is one of the two source files that hold the lists, so both are
exempt from their own scan (#81, Code B). Every literal that a scan must not
find lives here for that reason, including the legacy paths of `LEG-3`.

The other source file is `CONTEXT.md`. Ticket I11 of #90 points the prose scan
at the `_Avoid_` terms of that document, so the vocabulary of the target and the
list of retired words are one fact in one place. A document that states a banned
word is a document that a scan must skip, which is why `CONTEXT.md` joins this
module in `SOURCE_FILES`.

Two trees are exempt in both the Root Pack and a Terminal Project, because this
repository owns neither their words nor their files. `docs/vendored/` is a
read-only third-party documentation pin (clause A2 of #85), and `.agents/` holds
externally sourced agent skills that `skills-lock.json` pins. The gate itself
excludes the same two trees. One more exemption applies to the Root Pack only:
`CHANGELOG.md`, which records the pack's own history. A Terminal Project takes a
fresh `CHANGELOG.md` from `initial/`, so it needs no exemption of its own.

List 1 holds identifiers and paths, and it is case-sensitive over the whole
tree. It includes `--cov`, `pytest-cov` and `[tool.coverage`, so `LEG-1` also
proves that the line-coverage floor is gone. Nothing replaces it, and this suite
adds no coverage assertion anywhere (conflict C10 of #85).

Two identifiers that section 1.5 of #85 lists are absent from list 1 below. This
paragraph is the record of that decision, which ticket I11 owed.

* `schema_version` is the first key of `pack/proof/policy.toml`, of every proof
  catalog, of the `proof.toml` of each capability, and of the machine envelope
  that `_foundation/cli_protocol.py` writes.
* `proof_catalog` names three surviving modules of `pack/scripts/`, and ten more
  files import them.

Section 1.2 of #85 gives each of those files a surviving verdict, so section 1.5
banned the name of a file that the same deletion boundary keeps. The deleted
artifact that both entries aimed at is the derived index,
`proof/_generated/index.json`, whose own first key was `schema_version`. The
identifier `_generated` stays on the list and proves that the index is gone, so
no proof of deletion is lost. The alternative was a rename of a live catalog
schema key and of a published envelope field. That is a product change, and it
proves nothing about deletion.

List 2 holds prose, and it is case-insensitive over Markdown and Python only.
`prose_pattern` builds it from `CONTEXT.md` at scan time, plus
`EXTRA_PROSE_TERMS` below.
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
    "prose_pattern",
]

IDENTIFIER_PATTERN = (
    r"repoctl|copier|\.jinja|instantiate\.py|_generated|ownership_zone|ownership_policy"
    r"|ownership_guard|capability_validator|quality_gate\.py"
    r"|\bOWN00[1-5]\b|\bARCH02[45]\b|\bARCH031\b|\bCAP00[1-3]\b|\bN[012]\b"
    r"|pytest-cov|--cov|\[tool\.coverage"
)
PROSE_SUFFIXES = ("*.md", "*.py")
# The document that states the vocabulary of the target, and with it the words
# the target retired. It is the source of list 2.
VOCABULARY_FILE = "CONTEXT.md"
AVOID_PREFIX = "_Avoid_:"
# Two terms that name deleted machinery and that `CONTEXT.md` does not carry,
# because no surviving term replaces either one. Code B of #81 states both.
EXTRA_PROSE_TERMS = ("lifecycle state", "declaration file")
# Four `_Avoid_` terms that no word search can carry, and the reason for each.
# Each of the first three tells a writer which word not to use for one named
# concept, and each is an ordinary word for another concept in the same
# documents.
#
# * `generator` is also the name of a standard-library type.
# * `user code` and `capability code` are the correct words for the User-owned
#   Surface, and #85 uses both. `CONTEXT.md` retires them for one other concept,
#   the Pack-owned Surface, and a word search cannot make that judgment.
#
# `n0` is absent from list 2 for a different reason: list 1 already carries it,
# case-sensitive and over the whole tree rather than over prose alone.
#
# This set is residual risk 3 of #85 in executable form. `LEG-2` proves that the
# deleted vocabulary is absent, and it cannot prove that the surviving
# vocabulary is used correctly.
UNSEARCHABLE_TERMS = frozenset({"generator", "user code", "capability code", "n0"})
# The subsystems of `LEG-3`, which must exist on disk in neither tree. They sit
# beside the two lists because each name is also a banned identifier.
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
