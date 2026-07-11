"""UUID-backed item identifier factory."""

from uuid import uuid4

from __PACKAGE__.domain.value_objects import ItemId


def new_item_id() -> ItemId:
    """Create an opaque identifier at the outer boundary."""
    return ItemId(value=str(uuid4()))
