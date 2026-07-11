import pytest

from __PACKAGE__.adapters.inbound.cli import create_item_from_text
from __PACKAGE__.bootstrap import create_item_handler


@pytest.mark.integration
def test_composed_vertical_slice() -> None:
    event = create_item_from_text(create_item_handler(), "Wired item")

    assert event.name.value == "Wired item"
    assert event.item_id.value
