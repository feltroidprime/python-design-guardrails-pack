"""No inbound adapter of its own, by design.

The pack-owned router reads `api.py` and derives the whole command line from
the signatures and the docstrings there. A capability that wrote its own
command-line code would freeze one shape of it, so this package stays empty and
the router stays the one inbound adapter.
"""
