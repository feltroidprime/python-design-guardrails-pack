"""The two ban lists of Code B of #81, the legacy paths, and the exemptions.

This module is the source file that holds the lists, so it is exempt from its
own scan (#81, Code B). Every literal that a scan must not find lives here for
that reason, including the legacy paths of `LEG-3`.

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

List 2 holds prose, and it is case-insensitive over Markdown and Python only.
"""

__all__ = [
    "EXEMPT_IN_PACK",
    "GENERATED_DIRECTORY",
    "IDENTIFIER_PATTERN",
    "LEGACY_PATHS",
    "PROSE_PATTERN",
    "PROSE_SUFFIXES",
    "SOURCE_FILE",
    "UNOWNED_TREES",
]

IDENTIFIER_PATTERN = (
    r"repoctl|copier|\.jinja|instantiate\.py|_generated|ownership_zone|ownership_policy"
    r"|ownership_guard|capability_validator|quality_gate\.py|schema_version|proof_catalog"
    r"|\bOWN00[1-5]\b|\bARCH02[45]\b|\bARCH031\b|\bCAP00[1-3]\b|\bN[012]\b"
    r"|pytest-cov|--cov|\[tool\.coverage"
)
PROSE_PATTERN = (
    r"meta-repository|template tree|template directory|template rendering"
    r"|generated repository|recursive generation|self-replication|repository recursion"
    r"|nested repository|child repository|included repository|registered capability"
    r"|scaffold|self-update|lifecycle state|declaration file"
)
PROSE_SUFFIXES = ("*.md", "*.py")
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
# This module states the banned words, so a scan of it always finds them.
SOURCE_FILE = "ban_lists.py"
# Two trees whose words this repository does not own, in either project.
UNOWNED_TREES = ("docs/vendored", ".agents")
# The Root Pack keeps its own history. A Terminal Project starts a fresh one.
EXEMPT_IN_PACK = ("CHANGELOG.md",)
