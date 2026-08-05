"""The effects of the capability, on the outside of the application layer.

`inbound/` is empty by design: the pack-owned router is the one inbound adapter
of every capability, and it derives the command line from `api.py`.
`outbound/` holds the two effects this capability needs, the projection payload
and one local command.
"""
