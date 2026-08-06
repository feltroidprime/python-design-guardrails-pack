"""Adapters of the pack-owned foundation: empty by design.

`router.py` writes to the process boundary itself, through `sys.stdout` and
`sys.stderr`, so this package holds no adapter of its own. It stays in the
tree as the seam for a future inbound or outbound adapter. A capability never
imports it, because the whole `_foundation` surface is pack-owned and an
`import-linter` contract forbids that import.
"""
