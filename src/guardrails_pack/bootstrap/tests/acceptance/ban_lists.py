"""The two ban lists of Code B of #81, and the three exemptions they carry.

This module is the source file that holds the lists, so it is exempt from its
own scan (#81, Code B). Two more exemptions apply to the Root Pack only:
`CHANGELOG.md`, which records the pack's own history, and `docs/vendored/`,
which is a read-only third-party pin whose words the pack does not own (clause
A2 of #85). A Terminal Project takes a fresh `CHANGELOG.md` from `initial/`, so
it needs no exemption of its own.

List 1 holds identifiers and paths, and it is case-sensitive over the whole
tree. It includes `--cov`, `pytest-cov` and `[tool.coverage`, so `LEG-1` also
proves that the line-coverage floor is gone. Nothing replaces it, and this suite
adds no coverage assertion anywhere (conflict C10 of #85).

List 2 holds prose, and it is case-insensitive over Markdown and Python only.
"""

__all__ = ["EXEMPT_IN_PACK", "IDENTIFIER_PATTERN", "PROSE_PATTERN", "PROSE_SUFFIXES", "SOURCE_FILE"]

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
# This module states the banned words, so a scan of it always finds them.
SOURCE_FILE = "ban_lists.py"
# The Root Pack keeps its own history and a read-only third-party pin. Both hold
# words that the deletion retired, and neither one instructs a coding agent.
EXEMPT_IN_PACK = ("CHANGELOG.md", "docs/vendored")
