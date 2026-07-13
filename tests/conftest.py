"""Shared test bootstrap: import paths and template-pollution guard.

Runs before any test module is collected, so every module can import the
generator (`instantiate`), the pack scripts (`validate_pack`), and the
template guard package (`scripts.*` from template/) with plain imports.
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]

# Importing template/scripts must never drop a __pycache__ into template/
# (a forbidden local artifact per test_template_itself_contains_no_local_artifacts).
sys.dont_write_bytecode = True

for entry in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "template"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
