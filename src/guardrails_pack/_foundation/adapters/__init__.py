"""Adapters of the pack-owned foundation.

The foundation reaches the process boundary through this package. A capability
never imports it, because the whole `_foundation` surface is pack-owned and
protected by an `import-linter` contract (rule L4 of #85 section 4.3).
"""
