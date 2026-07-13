"""Audit-log reaction to domain events: an independent event consumer."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from __PACKAGE__.domain.events import ItemCreatedEvent

_logger = logging.getLogger(__name__)


def log_item_created(event: ItemCreatedEvent) -> None:
    """Record the created item in the audit log."""
    _logger.info(
        "item created: %s (%s) at %s",
        event.name.value,
        event.item_id.value,
        event.occurred_at.isoformat(),
    )
