"""Standalone durable epic-orchestration control plane.

Vendored from the Conductor orchestration harness. Pure standard library
except `compile_epic.py`, which needs `yamlrocks` to parse `epic.yaml`.
"""

from __future__ import annotations

import sys

from . import github_evidence as _github_evidence

# The modules use sibling absolute imports when executed as scripts. Keep that
# name resolvable when they are imported as a package instead.
sys.modules.setdefault("github_evidence", _github_evidence)
