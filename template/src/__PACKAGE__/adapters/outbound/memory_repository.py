"""In-memory repository for tests and local use."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from __PACKAGE__.domain.entities import Item
    from __PACKAGE__.domain.value_objects import ItemId


class MemoryItemRepository:
    """Store aggregate references in process memory."""

    def __init__(self) -> None:
        self._items: dict[ItemId, Item] = {}

    def get(self, item_id: ItemId) -> Item | None:
        return self._items.get(item_id)

    def save(self, item: Item) -> None:
        self._items[item.item_id] = item
