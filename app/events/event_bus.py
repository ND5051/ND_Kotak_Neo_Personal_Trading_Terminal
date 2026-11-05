from collections import defaultdict
import threading
from typing import Any, Callable, Dict, List

from app.events.event_types import Event
from app.logging.logger import get_logger

logger = get_logger("app.events.event_bus")


class EventBus:
    """
    Thread-safe in-memory publish-subscribe event broker.
    Ensures safe decoupling between modules without direct cross-dependency.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Register a handler callback for a specific event type."""
        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(
                    f"Subscribed handler '{handler.__name__}' to event '{event_type}'",
                    event="EVENT_SUBSCRIBE",
                    event_type=event_type,
                )

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]) -> bool:
        """Unregister a handler callback for an event type."""
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(
                    f"Unsubscribed handler '{handler.__name__}' from event '{event_type}'",
                    event="EVENT_UNSUBSCRIBE",
                    event_type=event_type,
                )
                return True
            return False

    def publish(self, event_type: str, data: Any = None) -> Event:
        """
        Publish an event to all registered subscribers.
        Catches subscriber exceptions to prevent handler failures from corrupting publisher flow.
        """
        payload_data = data if isinstance(data, dict) else {"payload": data}
        event = Event(event_type=event_type, data=payload_data)

        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        logger.info(
            f"Dispatching event '{event_type}' to {len(handlers)} handler(s)",
            event="EVENT_DISPATCH",
            event_type=event_type,
            handler_count=len(handlers),
        )

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error executing event handler '{handler.__name__}' for '{event_type}': {str(e)}",
                    event="EVENT_HANDLER_ERROR",
                    exc_info=True,
                    event_type=event_type,
                )

        return event

    def clear(self) -> None:
        """Remove all subscriptions (primarily used for unit test teardown)."""
        with self._lock:
            self._subscribers.clear()


# Default Global Singleton EventBus
event_bus = EventBus()


# Shorthand API
def publish(event_name: str, data: Any = None) -> Event:
    return event_bus.publish(event_name, data)


def subscribe(event_name: str, handler: Callable[[Event], None]) -> None:
    event_bus.subscribe(event_name, handler)


def unsubscribe(event_name: str, handler: Callable[[Event], None]) -> bool:
    return event_bus.unsubscribe(event_name, handler)

