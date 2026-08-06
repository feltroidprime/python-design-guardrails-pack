"""The composition root of this project.

This file is user-owned. `init` writes it once, and no pack update rewrites it.
It is the one user-owned module that the pack-owned router imports, so the
tuple below is the whole command surface: the router derives one command group
from each entry, and one subcommand from each public function of that entry.

An entry is a capability's `api` module, or the object that a factory in that
same `api.py` returns when the capability needs a bound port. Import presence
here replaces every status field: a capability directory that this file never
imports is uncomposed, which is legal.

Add a capability with one directory under this package and one import line
above this tuple. Nothing else records it.
"""

CAPABILITIES: tuple[object, ...] = ()
