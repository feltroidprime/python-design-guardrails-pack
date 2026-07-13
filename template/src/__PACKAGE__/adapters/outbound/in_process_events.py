"""In-process, synchronous delivery of domain events."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from __PACKAGE__.domain.events import DomainEvent


class InProcessEventPublisher:
    """Deliver each published event to every matching subscribed handler."""

    def __init__(self) -> None:
        self._dispatchers: list[Callable[[DomainEvent], None]] = []

    def subscribe[E: DomainEvent](self, event_type: type[E], handler: Callable[[E], None]) -> None:
        """Route events of *event_type* to *handler*; the handler stays precisely typed."""

        def dispatch(event: DomainEvent) -> None:
            if isinstance(event, event_type):
                handler(event)

        self._dispatchers.append(dispatch)

    def publish(self, event: DomainEvent) -> None:
        for dispatch in self._dispatchers:
            dispatch(event)
