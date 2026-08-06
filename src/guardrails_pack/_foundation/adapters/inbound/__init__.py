"""No inbound adapter of its own, by design.

The command line is the only inbound boundary this foundation owns, and
`router.py` reads it directly through `sys.argv`. A separate inbound adapter
adds one indirection and carries no request the router does not already read,
so this package stays empty.
"""
