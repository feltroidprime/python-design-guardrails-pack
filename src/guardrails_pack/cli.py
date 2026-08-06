"""The command-line entry point of this project.

This file is user-owned. The pack wrote it once, at the start of this project,
and no later pack update rewrites it. It names the pack-owned router and
nothing else, because every router feature is additive and reaches this
project without an edit here.
"""

from guardrails_pack._foundation.router import main

__all__ = ["main"]
