"""Capabilities required by application use cases."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from __PACKAGE__.domain.entities import Item
    from __PACKAGE__.domain.value_objects import ItemId


class ItemRepository(Protocol):
    """Persistence boundary for the Item aggregate."""

    def get(self, item_id: ItemId) -> Item | None:
        """Return an item when it exists."""
        ...

    def save(self, item: Item) -> None:
        """Persist the current aggregate state."""
        ...


type ItemIdFactory = Callable[[], ItemId]
