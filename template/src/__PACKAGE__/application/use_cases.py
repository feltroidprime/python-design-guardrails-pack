"""Application use cases."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from __PACKAGE__.domain.entities import Item
from __PACKAGE__.domain.events import ItemCreatedEvent
from __PACKAGE__.domain.value_objects import ItemName

if TYPE_CHECKING:
    from __PACKAGE__.application.ports import ItemIdFactory, ItemRepository


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateItemCommand:
    """Input accepted by the create-item use case."""

    name: str


class CreateItem:
    """Create and persist a validated Item aggregate."""

    def __init__(self, repository: ItemRepository, id_factory: ItemIdFactory) -> None:
        self._repository: ItemRepository = repository
        self._id_factory: ItemIdFactory = id_factory

    def __call__(self, command: CreateItemCommand) -> ItemCreatedEvent:
        item = Item(item_id=self._id_factory(), name=ItemName(value=command.name))
        self._repository.save(item)
        return ItemCreatedEvent(item_id=item.item_id, name=item.name)
