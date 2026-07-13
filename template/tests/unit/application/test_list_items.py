from collections.abc import Iterator

from __PACKAGE__.adapters.outbound.memory_repository import MemoryItemRepository
from __PACKAGE__.application.use_cases import ListItems
from __PACKAGE__.domain.entities import Item
from __PACKAGE__.domain.value_objects import ItemId, ItemName


def test_list_items_streams_stored_items() -> None:
    repository = MemoryItemRepository()
    repository.save(Item(item_id=ItemId(value="item-1"), name=ItemName(value="One")))
    handler = ListItems(repository=repository)

    items = handler()

    assert isinstance(items, Iterator)
    assert [item.name.value for item in items] == ["One"]
