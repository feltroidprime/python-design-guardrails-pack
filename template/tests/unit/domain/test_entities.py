from __PACKAGE__.domain.entities import Item
from __PACKAGE__.domain.value_objects import ItemId, ItemName


def test_rename_replaces_name_with_validated_value_object() -> None:
    item = Item(item_id=ItemId(value="item-1"), name=ItemName(value="Before"))

    item.rename(ItemName(value="  After  "))

    assert item.name.value == "After"
