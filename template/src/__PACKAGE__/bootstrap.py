"""Production composition root."""

from __PACKAGE__.adapters.outbound.memory_repository import MemoryItemRepository
from __PACKAGE__.adapters.outbound.uuid_ids import new_item_id
from __PACKAGE__.application.use_cases import CreateItem


def create_item_handler() -> CreateItem:
    """Wire the production dependency graph for the example slice."""
    return CreateItem(repository=MemoryItemRepository(), id_factory=new_item_id)
