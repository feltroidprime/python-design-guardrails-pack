"""Small CLI-facing translation adapter."""

from typing import TYPE_CHECKING

from __PACKAGE__.application.use_cases import CreateItem, CreateItemCommand

if TYPE_CHECKING:
    from __PACKAGE__.domain.events import ItemCreatedEvent


def create_item_from_text(handler: CreateItem, raw_name: str) -> ItemCreatedEvent:
    """Translate text input into the application command."""
    return handler(CreateItemCommand(name=raw_name))
