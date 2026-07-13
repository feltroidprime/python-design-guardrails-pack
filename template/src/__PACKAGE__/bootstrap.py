"""Production composition root: the only place that wires concrete adapters."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import sys
from typing import TYPE_CHECKING

from __PACKAGE__.adapters.inbound.cli import run
from __PACKAGE__.adapters.outbound.audit_log import log_item_created
from __PACKAGE__.adapters.outbound.in_process_events import InProcessEventPublisher
from __PACKAGE__.adapters.outbound.memory_repository import MemoryItemRepository
from __PACKAGE__.adapters.outbound.sqlite_repository import SqliteItemRepository
from __PACKAGE__.adapters.outbound.system_clock import utc_now
from __PACKAGE__.adapters.outbound.uuid_ids import new_item_id
from __PACKAGE__.application.use_cases import CreateItem, ListItems
from __PACKAGE__.domain.events import ItemCreatedEvent

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from __PACKAGE__.application.ports import ItemRepository

DEFAULT_DATABASE = Path("items.db")


@dataclass(frozen=True, slots=True, kw_only=True)
class Application:
    """The wired use-case handlers inbound adapters may call."""

    create_item: CreateItem
    list_items: ListItems


def build_application(repository: ItemRepository) -> Application:
    """Wire the dependency graph around one repository implementation."""
    events = InProcessEventPublisher()
    events.subscribe(ItemCreatedEvent, log_item_created)
    return Application(
        create_item=CreateItem(
            repository=repository, id_factory=new_item_id, clock=utc_now, events=events
        ),
        list_items=ListItems(repository=repository),
    )


def memory_application() -> Application:
    """Wire the application on the in-memory repository (tests and demos)."""
    return build_application(MemoryItemRepository())


@contextmanager
def sqlite_application(database: Path) -> Generator[Application]:
    """Own the SQLite connection lifecycle around a wired application."""
    connection = sqlite3.connect(database)
    try:
        yield build_application(SqliteItemRepository(connection))
    finally:
        connection.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the example CLI against the local SQLite database."""
    arguments = sys.argv[1:] if argv is None else list(argv)
    with sqlite_application(DEFAULT_DATABASE) as application:
        return run(
            arguments,
            create_item=application.create_item,
            list_items=application.list_items,
            out=sys.stdout,
            err=sys.stderr,
        )
