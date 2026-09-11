from collections.abc import Callable
from dataclasses import fields
from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

import pytest

from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.errors import CurrencyMismatchError
from goldy.domain.common.values.money import Money
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.errors import (
    CancellationReasonRequiredError,
    CustomerCannotCancelProcessedOrderError,
    EmptyOrderError,
    OrderNotEditableError,
    OrderStatusTransitionError,
)
from goldy.domain.orders.events import (
    OrderDeliveryAddressChanged,
    OrderPlaced,
    OrderStatusChanged,
)
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.order_status import OrderStatus
from tests.unit.factories.domain_factories import make_events_collection, make_user_id
from tests.unit.factories.shop_factories import (
    DELIVERY_ADDRESS,
    ORDER_NUMBER,
    PRICE_TYPE_ID,
    make_delivery_address,
    make_order,
    make_order_id,
    make_order_line,
    make_order_number,
    make_placement,
    make_price_type_id,
)
from tests.unit.support import drain, emitted_event_names, emitted_events

OTHER_ADDRESS: str = "Казань, улица Баумана, 10"

PRIMITIVE_TYPES: Final[tuple[type, ...]] = (str, int, bool, UUID, datetime, type(None))


def test_placing_an_order_starts_it_new_and_announces_it() -> None:
    order, collection = make_order()

    assert order.status is OrderStatus.NEW
    assert order.is_terminal is False
    assert emitted_event_names(collection) == ["OrderPlaced"]


def test_an_order_without_lines_is_refused() -> None:
    """Nothing to buy is not an order, and the total would be zero."""
    with pytest.raises(EmptyOrderError):
        Order.place(
            order_id=make_order_id(),
            order_number=make_order_number(),
            events_collection=make_events_collection(),
            placement=make_placement(lines=()),
        )


def test_an_order_mixing_currencies_is_refused() -> None:
    """Checked once at placement, which is what lets ``total`` add lines up blindly."""
    lines = (
        make_order_line(position=1, index=1, price="10.00", currency=Currency.RUB),
        make_order_line(position=2, index=2, price="10.00", currency=Currency.USD),
    )

    with pytest.raises(CurrencyMismatchError):
        Order.place(
            order_id=make_order_id(),
            order_number=make_order_number(),
            events_collection=make_events_collection(),
            placement=make_placement(lines=lines),
        )


def test_the_total_is_the_sum_of_the_lines() -> None:
    """Derived rather than stored, so it cannot disagree with the lines."""
    order, _ = make_order(
        lines=(
            make_order_line(position=1, index=1, price="19.99", quantity=3),
            make_order_line(position=2, index=2, price="0.50", quantity=2),
        ),
    )

    assert order.total == Money(Decimal("60.97"), Currency.RUB)
    assert order.total_quantity == 5


def test_an_order_keeps_the_price_type_it_was_priced_by() -> None:
    """Mandatory, because a customer is always on one price list or another.

    An optional field would guarantee only that some orders end up without one,
    and the price type is a mandatory attribute of a customer order in 1C.
    """
    order, _ = make_order()

    assert order.price_type_id == make_price_type_id()


def test_placing_an_order_announces_it_with_primitives() -> None:
    """The outbox serialises this row, so the total travels as a string.

    JSON has no ``Decimal``, and a float in an order total is a rounding error
    waiting for its moment.
    """
    order, collection = make_order(
        lines=(make_order_line(position=1, index=1, price="19.99", quantity=3),),
    )

    placed = emitted_events(collection)[0]

    assert isinstance(placed, OrderPlaced)
    assert placed.order_id == order.id
    assert placed.order_number == ORDER_NUMBER
    assert placed.customer_id == make_user_id()
    assert placed.price_type_id == PRICE_TYPE_ID
    assert placed.total_amount == "59.97"
    assert placed.currency == "rub"
    assert placed.line_count == 1


def test_placing_an_order_announces_no_personal_data() -> None:
    """The outbox row is published to a topic exchange with no consumer yet.

    Spreading somebody's address and telephone number across queues "for later"
    is free only until the first incident review; whoever needs them reads the
    order by its id.
    """
    _, collection = make_order()

    placed = emitted_events(collection)[0]
    announced = {attribute.name for attribute in fields(placed)}

    assert announced == {
        "event_id",
        "event_date",
        "order_id",
        "order_number",
        "customer_id",
        "price_type_id",
        "total_amount",
        "currency",
        "line_count",
    }


def test_order_events_carry_primitives_and_not_value_objects() -> None:
    order, collection = make_order()
    order.change_delivery_address(make_delivery_address(OTHER_ADDRESS))
    order.confirm()
    order.ship()
    order.complete()
    _, cancelled_collection = make_order(status=OrderStatus.CANCELLED)

    events = emitted_events(collection) + emitted_events(cancelled_collection)

    assert len(events) == 7
    assert all(
        isinstance(getattr(event, attribute.name), PRIMITIVE_TYPES)
        for event in events
        for attribute in fields(event)
    )


@pytest.mark.parametrize(
    ("status", "transition", "expected"),
    (
        (OrderStatus.NEW, Order.confirm, OrderStatus.CONFIRMED),
        (OrderStatus.CONFIRMED, Order.ship, OrderStatus.SHIPPED),
        (OrderStatus.SHIPPED, Order.complete, OrderStatus.COMPLETED),
    ),
)
def test_every_step_the_table_allows_is_taken_and_announced(
    status: OrderStatus,
    transition: Callable[[Order], None],
    expected: OrderStatus,
) -> None:
    """One event for every move, whatever the move is.

    Four events for four transitions would oblige a consumer to know that
    ``OrderCancelled`` and a status change to ``cancelled`` are one thing, and
    sooner or later the customer gets told twice.
    """
    order, collection = make_order(status=status)
    drain(collection)

    transition(order)

    changed = emitted_events(collection)[0]
    assert order.status is expected
    assert isinstance(changed, OrderStatusChanged)
    assert changed.old_status == status.value
    assert changed.new_status == expected.value
    assert changed.reason is None


@pytest.mark.parametrize(
    ("status", "transition"),
    (
        (OrderStatus.NEW, Order.ship),
        (OrderStatus.NEW, Order.complete),
        (OrderStatus.CONFIRMED, Order.confirm),
        (OrderStatus.CONFIRMED, Order.complete),
        (OrderStatus.SHIPPED, Order.confirm),
        (OrderStatus.SHIPPED, Order.ship),
        (OrderStatus.COMPLETED, Order.confirm),
        (OrderStatus.COMPLETED, Order.ship),
        (OrderStatus.COMPLETED, Order.complete),
        (OrderStatus.CANCELLED, Order.confirm),
        (OrderStatus.CANCELLED, Order.ship),
        (OrderStatus.CANCELLED, Order.complete),
    ),
)
def test_every_step_the_table_forbids_is_refused(
    status: OrderStatus,
    transition: Callable[[Order], None],
) -> None:
    """Including every move out of a finished order, which has none left."""
    order, _ = make_order(status=status)

    with pytest.raises(OrderStatusTransitionError):
        transition(order)


def test_a_refused_step_leaves_the_status_where_it_was() -> None:
    order, collection = make_order(status=OrderStatus.CONFIRMED)
    drain(collection)

    with pytest.raises(OrderStatusTransitionError):
        order.complete()

    assert order.status is OrderStatus.CONFIRMED
    assert emitted_event_names(collection) == []


@pytest.mark.parametrize("status", (OrderStatus.NEW, OrderStatus.CONFIRMED))
def test_a_customer_may_withdraw_an_order_that_has_not_left_the_shop(
    status: OrderStatus,
) -> None:
    """Confirmation does not take the right to change their mind away.

    It only means the order was accepted for picking; after ``SHIPPED`` it
    would be a return, and returns do not live in the bot.
    """
    order, collection = make_order(status=status)
    drain(collection)

    order.cancel(initiated_by=CancellationInitiator.CUSTOMER)

    assert order.status is OrderStatus.CANCELLED
    assert order.cancelled_by is CancellationInitiator.CUSTOMER
    assert order.cancellation_reason is None
    assert emitted_event_names(collection) == ["OrderStatusChanged"]


@pytest.mark.parametrize(
    "status",
    (OrderStatus.SHIPPED, OrderStatus.COMPLETED, OrderStatus.CANCELLED),
)
def test_a_customer_cannot_withdraw_an_order_that_is_already_on_its_way(
    status: OrderStatus,
) -> None:
    """Once the parcel has left, stopping it is a return, not a button."""
    order, _ = make_order(status=status)

    with pytest.raises(CustomerCannotCancelProcessedOrderError):
        order.cancel(initiated_by=CancellationInitiator.CUSTOMER)


@pytest.mark.parametrize(
    "status",
    (OrderStatus.NEW, OrderStatus.CONFIRMED, OrderStatus.SHIPPED),
)
def test_a_manager_may_stop_any_unfinished_order(status: OrderStatus) -> None:
    """Cancelling a shipped order is allowed: a courier does come back with the parcel."""
    order, collection = make_order(status=status)
    drain(collection)
    reason = CancellationReason(value="Товара не оказалось на складе")

    order.cancel(initiated_by=CancellationInitiator.MANAGER, reason=reason)

    assert order.status is OrderStatus.CANCELLED
    assert order.cancellation_reason == reason
    assert emitted_event_names(collection) == ["OrderStatusChanged"]


@pytest.mark.parametrize("status", (OrderStatus.COMPLETED, OrderStatus.CANCELLED))
def test_a_finished_order_cannot_be_cancelled_even_by_a_manager(
    status: OrderStatus,
) -> None:
    order, _ = make_order(status=status)
    reason = CancellationReason(value="Передумали")

    with pytest.raises(OrderStatusTransitionError):
        order.cancel(initiated_by=CancellationInitiator.MANAGER, reason=reason)


def test_a_manager_has_to_say_why() -> None:
    """The customer is about to be told, and "cancelled" alone explains nothing."""
    order, _ = make_order()

    with pytest.raises(CancellationReasonRequiredError):
        order.cancel(initiated_by=CancellationInitiator.MANAGER)


def test_a_cancellation_announces_the_move_and_the_reason() -> None:
    """The reason is text the customer is shown, so it travels with the fact.

    Who cancelled does not: ``confirm``, ``ship`` and ``complete`` take no
    arguments and would have nothing to fill such a field from, so the author
    stays on the aggregate as ``cancelled_by``.
    """
    order, collection = make_order()
    drain(collection)

    order.cancel(
        initiated_by=CancellationInitiator.MANAGER,
        reason=CancellationReason(value="Нет на складе"),
    )

    cancelled = emitted_events(collection)[0]
    assert isinstance(cancelled, OrderStatusChanged)
    assert cancelled.old_status == "new"
    assert cancelled.new_status == "cancelled"
    assert cancelled.reason == "Нет на складе"
    assert order.cancelled_by is CancellationInitiator.MANAGER


@pytest.mark.parametrize("status", (OrderStatus.NEW, OrderStatus.CONFIRMED))
def test_changing_the_delivery_address_announces_both_addresses(
    status: OrderStatus,
) -> None:
    """Whoever is about to print a label needs to know it moved.

    Both editable statuses, because a confirmed order is exactly the case the
    announcement exists for: the manager has already taken it on.
    """
    order, collection = make_order(status=status)
    drain(collection)

    order.change_delivery_address(make_delivery_address(OTHER_ADDRESS))

    changed = emitted_events(collection)[0]
    assert str(order.delivery_address) == OTHER_ADDRESS
    assert isinstance(changed, OrderDeliveryAddressChanged)
    assert changed.old_address == DELIVERY_ADDRESS
    assert changed.new_address == OTHER_ADDRESS


def test_the_address_change_announces_the_addresses_and_nothing_else() -> None:
    """The one deliberate exception to "no personal data in events".

    An address is the whole content of this fact, so a move announced without
    saying where from and where to announces nothing anybody can act on, while
    ``OrderPlaced`` carried the address as a passenger. The exception stops at
    the address: no recipient name and no telephone number travel with it, and
    widening this set means changing ``docs/design/ordering.md`` first.
    """
    order, collection = make_order()
    drain(collection)

    order.change_delivery_address(make_delivery_address(OTHER_ADDRESS))

    changed = emitted_events(collection)[0]
    announced = {attribute.name for attribute in fields(changed)}
    assert announced == {
        "event_id",
        "event_date",
        "order_id",
        "order_number",
        "customer_id",
        "old_address",
        "new_address",
    }


def test_changing_the_address_to_the_one_it_already_has_announces_nothing() -> None:
    order, collection = make_order()
    drain(collection)

    order.change_delivery_address(make_delivery_address())

    assert emitted_event_names(collection) == []


@pytest.mark.parametrize(
    "status",
    (OrderStatus.SHIPPED, OrderStatus.COMPLETED, OrderStatus.CANCELLED),
)
def test_the_address_of_a_dispatched_order_cannot_be_changed(
    status: OrderStatus,
) -> None:
    """Refused before the address is even compared.

    Otherwise "changing" a shipped order to the address it already has would
    pass quietly, and presentation could read that as permission to offer the
    edit at all.
    """
    order, _ = make_order(status=status)

    with pytest.raises(OrderNotEditableError):
        order.change_delivery_address(make_delivery_address())


@pytest.mark.parametrize(
    ("status", "terminal", "cancellable"),
    (
        (OrderStatus.NEW, False, True),
        (OrderStatus.CONFIRMED, False, True),
        (OrderStatus.SHIPPED, False, False),
        (OrderStatus.COMPLETED, True, False),
        (OrderStatus.CANCELLED, True, False),
    ),
)
def test_the_order_answers_what_the_views_ask_it(
    status: OrderStatus,
    *,
    terminal: bool,
    cancellable: bool,
) -> None:
    """The cancel button hides by exactly the rule the aggregate refuses by."""
    order, _ = make_order(status=status)

    assert order.is_terminal is terminal
    assert order.can_customer_cancel is cancellable


def test_the_whole_lifecycle_announces_its_facts_in_order() -> None:
    order, collection = make_order()
    order.confirm()
    order.ship()
    order.complete()

    assert emitted_event_names(collection) == [
        "OrderPlaced",
        "OrderStatusChanged",
        "OrderStatusChanged",
        "OrderStatusChanged",
    ]
