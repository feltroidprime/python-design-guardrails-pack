from hypothesis import given, strategies as st
import pytest

from __PACKAGE__.domain.errors import InvalidItemNameError
from __PACKAGE__.domain.value_objects import MAX_ITEM_NAME_LENGTH, ItemId, ItemName


def test_item_id_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        _ = ItemId(value="   ")


def test_item_name_normalizes_outer_whitespace() -> None:
    assert ItemName(value="  useful name  ").value == "useful name"


def test_item_name_rejects_overlong_value() -> None:
    with pytest.raises(InvalidItemNameError, match=f"at most {MAX_ITEM_NAME_LENGTH} characters"):
        _ = ItemName(value="x" * (MAX_ITEM_NAME_LENGTH + 1))


@given(st.text().filter(lambda value: not value.strip()))
def test_item_name_rejects_every_blank_string(value: str) -> None:
    with pytest.raises(InvalidItemNameError):
        _ = ItemName(value=value)
