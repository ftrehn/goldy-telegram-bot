from .order_event_consumers import (
    ORDER_ADDRESS_QUEUE,
    ORDER_PLACED_QUEUE,
    ORDER_STATUS_QUEUE,
    OrderEventConsumers,
    setup_order_event_consumers,
)

__all__ = [
    "ORDER_ADDRESS_QUEUE",
    "ORDER_PLACED_QUEUE",
    "ORDER_STATUS_QUEUE",
    "OrderEventConsumers",
    "setup_order_event_consumers",
]
