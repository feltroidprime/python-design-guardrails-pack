"""Command-line inbound adapter.

Inbound adapters translate the outside world (here: argv and text streams)
into application calls, and translate failures back into stable exit codes.
"""

from typing import TYPE_CHECKING

from __PACKAGE__.application.use_cases import CreateItemCommand
from __PACKAGE__.domain.errors import DomainError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO

    from __PACKAGE__.application.use_cases import CreateItem, ListItems

USAGE = """usage: python -m __PACKAGE__ add <name>
       python -m __PACKAGE__ list
"""


def run(
    argv: Sequence[str],
    *,
    create_item: CreateItem,
    list_items: ListItems,
    out: TextIO,
    err: TextIO,
) -> int:
    """Translate one command-line invocation into use-case calls."""
    match list(argv):
        case ["add", raw_name]:
            return _add(raw_name, create_item=create_item, out=out, err=err)
        case ["list"]:
            for item in list_items():
                _ = out.write(f"{item.item_id.value}\t{item.name.value}\n")
            return 0
        case _:
            _ = err.write(USAGE)
            return 2


def _add(raw_name: str, *, create_item: CreateItem, out: TextIO, err: TextIO) -> int:
    try:
        event = create_item(CreateItemCommand(name=raw_name))
    except DomainError as error:
        _ = err.write(f"error: {error}\n")
        return 1
    _ = out.write(f"created {event.item_id.value}\t{event.name.value}\n")
    return 0
