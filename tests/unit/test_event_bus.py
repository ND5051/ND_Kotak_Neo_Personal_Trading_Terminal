from app.events.event_bus import EventBus
from app.events.event_types import Event, ORDER_CREATED


def test_event_bus_publish_subscribe():
    """Verify publish and subscribe mechanisms."""
    bus = EventBus()
    received_events = []

    def on_order_created(event: Event):
        received_events.append(event)

    bus.subscribe(ORDER_CREATED, on_order_created)
    published = bus.publish(ORDER_CREATED, {"order_id": "ORD-12345"})

    assert len(received_events) == 1
    assert received_events[0].event_type == ORDER_CREATED
    assert received_events[0].data["order_id"] == "ORD-12345"
    assert received_events[0].event_id == published.event_id


def test_event_bus_unsubscribe():
    """Verify handler unsubscription stops further invocations."""
    bus = EventBus()
    call_count = [0]

    def handler(event: Event):
        call_count[0] += 1

    bus.subscribe("SAMPLE_EVENT", handler)
    bus.publish("SAMPLE_EVENT", {})
    assert call_count[0] == 1

    assert bus.unsubscribe("SAMPLE_EVENT", handler) is True
    bus.publish("SAMPLE_EVENT", {})
    assert call_count[0] == 1


def test_event_bus_handler_isolation_on_exception():
    """Verify that an exception in one handler does not stop other handlers."""
    bus = EventBus()
    successful_calls = [0]

    def broken_handler(event: Event):
        raise ValueError("Simulated handler crash")

    def healthy_handler(event: Event):
        successful_calls[0] += 1

    bus.subscribe("SAMPLE_EVENT", broken_handler)
    bus.subscribe("SAMPLE_EVENT", healthy_handler)

    bus.publish("SAMPLE_EVENT", {})
    assert successful_calls[0] == 1

