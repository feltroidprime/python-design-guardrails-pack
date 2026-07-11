"""Immutable facts emitted by the domain/application boundary."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from __PACKAGE__.domain.value_objects import ItemId, ItemName


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemCreatedEvent:
    """Fact that an item was successfully created."""

    item_id: ItemId
    name: ItemName
