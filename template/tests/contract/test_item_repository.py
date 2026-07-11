from typing import TYPE_CHECKING

import pytest

from __PACKAGE__.adapters.outbound.memory_repository import MemoryItemRepository
from __PACKAGE__.domain.entities import Item
from __PACKAGE__.domain.value_objects import ItemId, ItemName

if TYPE_CHECKING:
    from __PACKAGE__.application.ports import ItemRepository


@pytest.fixture
def repository() -> ItemRepository:
    return MemoryItemRepository()


@pytest.mark.contract
def test_repository_round_trip(repository: ItemRepository) -> None:
    item = Item(item_id=ItemId(value="contract-1"), name=ItemName(value="Contract"))

    repository.save(item)

    assert repository.get(item.item_id) == item


@pytest.mark.contract
def test_repository_returns_none_for_unknown_id(repository: ItemRepository) -> None:
    assert repository.get(ItemId(value="missing")) is None
