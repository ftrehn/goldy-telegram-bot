from dataclasses import dataclass
from uuid import UUID

from goldy.domain.common.event import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPlaced(Event):
    """A cart became an order — the one business fact in the whole checkout.

    ``total_amount`` travels as a string rather than a number: JSON has no
    ``Decimal``, the serialiser knows dumpers for ``UUID`` and ``datetime``
    only, and turning a total into a ``float`` would lose kopecks on large
    amounts without anything failing.

    No personal data here — no delivery address, no recipient name, no phone.
    The event is written to the outbox and published to a RabbitMQ exchange
    that has no consumer yet, and spreading somebody's address and telephone
    number across queues "for later" is free only until the first incident
    review. Whoever needs them reads the order by its id.

    No order lines either, for the neighbouring reason: an event announces a
    fact, the document holds the state, and thirty lines copied into the outbox
    would become a second source of truth that drifts from the order itself.
    """

    order_id: UUID
    order_number: str
    customer_id: UUID
    price_type_id: str
    total_amount: str
    currency: str
    line_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderStatusChanged(Event):
    """The order moved along its lifecycle, cancellation included.

    One event for all four transitions rather than one per transition.
    Cancelling is a move of the status and not a different kind of fact, and a
    consumer obliged to know that ``OrderCancelled`` and this event with
    ``new_status="cancelled"`` mean the same thing eventually sends the
    customer two messages about one thing.

    There is no ``initiated_by``: ``confirm``, ``ship`` and ``complete`` take
    no arguments, so there would be nothing to fill it from, and widening three
    signatures for a field the aggregate already holds buys nothing. Who
    cancelled is ``Order.cancelled_by``, read by id like the lines are.
    ``reason`` stays because it is text the customer is shown.

    ``customer_id`` is on every order event so the notification worker knows
    who to write to without loading the order first.
    """

    order_id: UUID
    order_number: str
    customer_id: UUID
    old_status: str
    new_status: str
    reason: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderDeliveryAddressChanged(Event):
    """The order is going somewhere else than it was going.

    Survives the collapse into ``OrderStatusChanged`` because editing an
    address is not a transition, and a manager who has already taken the order
    on has to learn about it — this is precisely a fact somebody reacts to.

    The two addresses are the one deliberate exception to the rule that keeps
    personal data out of ``OrderPlaced``, and the exception is narrow: an
    address is the whole content of this fact, so an event announcing a move
    without saying where from and where to announces nothing a consumer could
    act on, whereas ``OrderPlaced`` carried the address as a passenger beside
    the fact it was actually reporting. Both are named by the events table in
    ``docs/design/ordering.md``, which is where the decision lives. Do not
    quietly drop these fields or quietly add a phone number beside them —
    either way round, change the design document first. No recipient name and
    no telephone number here for that reason.
    """

    order_id: UUID
    order_number: str
    customer_id: UUID
    old_address: str
    new_address: str
