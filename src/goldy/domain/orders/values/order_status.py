from enum import StrEnum


class OrderStatus(StrEnum):
    """The stage an order has reached.

    It describes the fate of the goods, nothing else. There is no ``PAID``
    because settlement happens outside the bot and a payment state in the model
    would immediately raise "who sets it", dragging half a payment flow behind
    it. There is no ``EXPORTED`` either: whether the order has reached 1C is the
    state of an integration, the outbox already tracks it, and folding it in
    here would produce an order that is "sent to 1C" while nobody can tell
    whether it has been shipped.

    Deliberately no ``is_terminal`` property. Which transitions are allowed is
    stated once, in ``status_transitions``, and a second statement of the same
    rule would drift from it on the first edit — the reasoning ``UserRole``
    already follows.
    """

    NEW = "new"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
