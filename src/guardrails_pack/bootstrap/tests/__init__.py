"""The tests of the One-shot Bootstrap, and the small pack tree they drive.

This package is importable so that one shared kit in `conftest.py` reaches every
module here by its absolute name. The repository bans a relative import, and a
capability's tests sit inside the package rather than beside it.

Ticket I10 adds `acceptance/` below this package. Those assertions carry the
`acceptance` marker, the `tests` hook of the gate excludes that marker, and
Terminal Projection deletes the whole capability with them.
"""
