from __PACKAGE__.adapters.outbound.memory_repository import MemoryItemRepository
from __PACKAGE__.application.use_cases import CreateItem, CreateItemCommand
from __PACKAGE__.domain.value_objects import ItemId


def test_create_item_persists_validated_aggregate() -> None:
    repository = MemoryItemRepository()
    expected_id = ItemId(value="item-1")
    handler = CreateItem(repository=repository, id_factory=lambda: expected_id)

    event = handler(CreateItemCommand(name="  First item  "))

    saved = repository.get(expected_id)
    assert saved is not None
    assert saved.name.value == "First item"
    assert event.item_id == expected_id
