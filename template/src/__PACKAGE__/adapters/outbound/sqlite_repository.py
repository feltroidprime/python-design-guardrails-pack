"""SQLite-backed repository: the reference outbound adapter.

Every future outbound adapter follows this shape: depend on an injected
resource, translate driver failures into the application-owned error while
preserving causes, and leave lifecycle to the composition root.
"""

import sqlite3
from typing import TYPE_CHECKING, cast

from __PACKAGE__.application.errors import RepositoryError
from __PACKAGE__.domain.entities import Item
from __PACKAGE__.domain.value_objects import ItemId, ItemName

if TYPE_CHECKING:
    from collections.abc import Iterator

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    name TEXT NOT NULL
)
"""
_UPSERT = """
INSERT INTO items (item_id, name) VALUES (?, ?)
ON CONFLICT (item_id) DO UPDATE SET name = excluded.name
"""
_SELECT_ONE = "SELECT item_id, name FROM items WHERE item_id = ?"
_SELECT_ALL = "SELECT item_id, name FROM items ORDER BY item_id"


def _decode(row: object) -> Item:
    match row:
        case (str(raw_id), str(raw_name)):
            return Item(item_id=ItemId(value=raw_id), name=ItemName(value=raw_name))
        case _:
            raise RepositoryError(f"Unexpected items row shape: {row!r}")


def _fetch_row(cursor: sqlite3.Cursor) -> object | None:
    try:
        row = cast("object | None", cursor.fetchone())
    except sqlite3.Error as error:
        raise RepositoryError("Could not read the next items row.") from error
    return row


class SqliteItemRepository:
    """Store items in an injected SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection: sqlite3.Connection = connection
        _ = self._execute(_CREATE_TABLE)

    def get(self, item_id: ItemId) -> Item | None:
        row = _fetch_row(self._execute(_SELECT_ONE, (item_id.value,)))
        return None if row is None else _decode(row)

    def save(self, item: Item) -> None:
        try:
            with self._connection:
                _ = self._connection.execute(_UPSERT, (item.item_id.value, item.name.value))
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not save item '{item.item_id.value}'.") from error

    def list_all(self) -> Iterator[Item]:
        cursor = self._execute(_SELECT_ALL)
        while (row := _fetch_row(cursor)) is not None:
            yield _decode(row)

    def _execute(self, statement: str, parameters: tuple[str, ...] = ()) -> sqlite3.Cursor:
        try:
            cursor = self._connection.execute(statement, parameters)
        except sqlite3.Error as error:
            raise RepositoryError("The items store rejected the operation.") from error
        return cursor
