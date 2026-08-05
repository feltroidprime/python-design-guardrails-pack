"""The command-line entry point of this project.

This file is user-owned. `init` writes it once, and no pack update rewrites it,
so it stays this project's own entry point for ever. It names the pack-owned
router and nothing else, because every router feature is additive and reaches
this project without an edit here.
"""

from guardrails_pack._foundation.router import main

__all__ = ["main"]
