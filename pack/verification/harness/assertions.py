"""Named proof oracles carrying the property ID into every failure."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def assert_property(*, condition: bool, property_id: str) -> None:
    """Fail with the stable property ID when an executable law is false."""
    if not condition:
        raise AssertionError(f"{property_id}: property is false")


def assert_falsifies(*, condition: bool, property_id: str) -> None:
    """Fail when a declared counterexample does not actually falsify its law."""
    if condition:
        raise AssertionError(f"{property_id}: canary no longer falsifies the property")


def assert_rejected(
    operation: Callable[[], object],
    exception_type: type[BaseException] | tuple[type[BaseException], ...],
    *,
    property_id: str,
) -> None:
    """Assert that one invalid candidate is rejected at the boundary."""
    try:
        _ = operation()
    except exception_type:
        return
    expected = (
        exception_type.__name__
        if isinstance(exception_type, type)
        else " | ".join(candidate.__name__ for candidate in exception_type)
    )
    raise AssertionError(f"{property_id}: expected rejection by {expected}")
