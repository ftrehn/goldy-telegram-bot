from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self, final

from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.common.aggregate import Aggregate
from goldy.domain.common.values.errors import CurrencyMismatchError
from goldy.domain.common.values.money import Money
from goldy.domain.orders.entities.order_line import OrderLine
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
from goldy.domain.orders.status_transitions import (
    ALLOWED_ORDER_TRANSITIONS,
    CUSTOMER_CANCELLABLE_STATUSES,
    EDITABLE_ORDER_STATUSES,
    TERMINAL_ORDER_STATUSES,
)
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_comment import OrderComment
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_number import OrderNumber
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.orders.values.recipient import Recipient
from goldy.domain.users.values.user_id import UserId

if TYPE_CHECKING:
    from goldy.domain.common.event import Event
    from goldy.domain.common.events_collection import EventsCollection
    from goldy.domain.orders.placement import Placement


def _ensure_single_currency(lines: Sequence[OrderLine]) -> None:
    """Refuses a set of lines priced in more than one currency.

    Checked here, once, and never again: the lines of a placed order do not
    change, so from this point on ``Order.total`` can add them up without
    asking the question a second time.

    Raises:
        CurrencyMismatchError: the lines are not all in one currency.
    """
    currencies = {line.unit_price.currency for line in lines}

    if len(currencies) > 1:
        named = ", ".join(sorted(currency.value for currency in currencies))
        msg = f"An order cannot mix currencies, got: {named}."
        raise CurrencyMismatchError(msg)


@final
@dataclass(eq=False, kw_only=True)
class Order(Aggregate[OrderId]):
    """An intention to buy, fixed at the moment the customer committed to it.

    Lines are snapshots, so the order keeps showing what was agreed however far
    the catalog moves on afterwards. Because those lines never change once
    placed, :attr:`total` is derived from them rather than stored: a computed
    property cannot disagree with the lines it is computed from, whereas a
    column can, and nothing would fail until somebody compared the two. Any
    future method that edits the contents of a placed order has to be written
    with that in mind.

    :attr:`price_type_id` is mandatory. The pricing service always resolves a
    price type by construction — the one bound to the customer, or the one
    configured as the default — and the case "no price list is configured at
    all" is refused earlier, with an error. An optional field here would
    guarantee only that some orders end up without one, and the future export
    to 1C, where a customer order's price type is a mandatory attribute, would
    run into documents there is nothing to fill it from.

    There is no payment state here at all — settlement happens outside the bot.
    There is no "exported to 1C" state either: that is the state of an
    integration, and the outbox already holds it.

    Delivery is free by construction today, which is why :attr:`total` is the
    sum of the lines and nothing else. A delivery charge would mean splitting
    it into an items total and a shipping cost, and inventing both before there
    is anything to put in them reads worse than the one future edit.

    Who is allowed to do any of this is not decided here: ownership and staff
    access are ``IsOrderOwner`` and ``CanManageOrders`` in
    ``services/authorization/permission.py``. One mechanism, so that
    ``GetOrderQuery`` can write ``AnyOf`` over the two halves of one rule.
    """

    number: OrderNumber
    customer_id: UserId
    delivery_address: DeliveryAddress
    recipient: Recipient
    price_type_id: PriceTypeId
    status: OrderStatus = field(default=OrderStatus.NEW)
    lines: list[OrderLine] = field(default_factory=list)
    comment: OrderComment | None = field(default=None)
    cancellation_reason: CancellationReason | None = field(default=None)
    cancelled_by: CancellationInitiator | None = field(default=None)

    @classmethod
    def place(
        cls,
        *,
        order_id: OrderId,
        order_number: OrderNumber,
        events_collection: EventsCollection,
        placement: Placement,
    ) -> Self:
        """Creates the order from finished lines and records ``OrderPlaced``.

        Raises:
            EmptyOrderError: there are no lines, so there is nothing to buy.
            CurrencyMismatchError: the lines are priced in more than one
                currency.
        """
        if not placement.lines:
            msg = f"Order '{order_number}' must have at least one line."
            raise EmptyOrderError(msg)

        _ensure_single_currency(placement.lines)

        order = cls(
            id=order_id,
            events_collection=events_collection,
            number=order_number,
            customer_id=placement.customer_id,
            delivery_address=placement.delivery_address,
            recipient=placement.recipient,
            lines=list(placement.lines),
            comment=placement.comment,
            price_type_id=placement.price_type_id,
        )
        order.events_collection.add_event(
            OrderPlaced(
                order_id=order_id,
                order_number=str(order_number),
                customer_id=placement.customer_id,
                price_type_id=str(placement.price_type_id),
                total_amount=str(order.total.amount),
                currency=order.total.currency.value,
                line_count=len(order.lines),
            ),
        )
        return order

    def confirm(self) -> None:
        """The shop accepted the order, having checked the real stock.

        Raises:
            OrderStatusTransitionError: the order is not in a state it can be
                confirmed from.
        """
        self._change_status(OrderStatus.CONFIRMED)

    def ship(self) -> None:
        """The goods left the shop.

        Raises:
            OrderStatusTransitionError: the order is not in a state it can be
                shipped from.
        """
        self._change_status(OrderStatus.SHIPPED)

    def complete(self) -> None:
        """The customer has the goods and the order is done.

        Raises:
            OrderStatusTransitionError: the order is not in a state it can be
                completed from.
        """
        self._change_status(OrderStatus.COMPLETED)

    def cancel(
        self,
        *,
        initiated_by: CancellationInitiator,
        reason: CancellationReason | None = None,
    ) -> None:
        """Stops the order, recording who stopped it and why.

        The two initiators are held to different rules, and both are decidable
        from this aggregate's own fields plus the initiator handed in. A
        customer may withdraw an order that has not left the shop yet — being
        confirmed does not take that right away, it only means the order was
        accepted for picking. A manager may stop anything unfinished but has to
        say why, because the customer is about to be told and "cancelled" on
        its own explains nothing.

        Raises:
            CustomerCannotCancelProcessedOrderError: the customer is trying to
                cancel an order that has already been dispatched.
            CancellationReasonRequiredError: a manager gave no reason.
            OrderStatusTransitionError: the order is already finished.
        """
        if (
            initiated_by is CancellationInitiator.CUSTOMER
            and self.status not in CUSTOMER_CANCELLABLE_STATUSES
        ):
            msg = (
                f"Order '{self.number}' is {self.status.value} and can no "
                f"longer be cancelled by the customer."
            )
            raise CustomerCannotCancelProcessedOrderError(msg)

        if initiated_by is CancellationInitiator.MANAGER and reason is None:
            msg = f"Cancelling order '{self.number}' as staff requires a reason."
            raise CancellationReasonRequiredError(msg)

        self._change_status(OrderStatus.CANCELLED, reason=reason)
        self.cancelled_by = initiated_by
        self.cancellation_reason = reason

    def change_delivery_address(self, delivery_address: DeliveryAddress) -> None:
        """Sends the order somewhere else.

        Raises:
            OrderNotEditableError: the parcel is already on its way or the
                order is finished, so the address on it is settled.
        """
        if self.status not in EDITABLE_ORDER_STATUSES:
            msg = (
                f"Order '{self.number}' is {self.status.value} and can no "
                f"longer be edited."
            )
            raise OrderNotEditableError(msg)

        if delivery_address == self.delivery_address:
            return

        old_address = self.delivery_address
        self.delivery_address = delivery_address
        self._touch()
        self._record(
            OrderDeliveryAddressChanged(
                order_id=self.id,
                order_number=str(self.number),
                customer_id=self.customer_id,
                old_address=str(old_address),
                new_address=str(delivery_address),
            ),
        )

    @property
    def total(self) -> Money:
        """What the whole order comes to, derived from the lines every time.

        The currency comes from the first line, which is safe because
        ``place`` refused a mixed-currency order once and the lines have not
        changed since.
        """
        if not self.lines:
            return Money.zero()

        total = Money.zero(self.lines[0].unit_price.currency)

        for line in self.lines:
            total += line.total

        return total

    @property
    def total_quantity(self) -> int:
        return sum(line.quantity.value for line in self.lines)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_ORDER_STATUSES

    @property
    def can_customer_cancel(self) -> bool:
        return self.status in CUSTOMER_CANCELLABLE_STATUSES

    def _change_status(
        self,
        status: OrderStatus,
        reason: CancellationReason | None = None,
    ) -> None:
        """Moves the order and announces the move, in that order.

        One announcement for all four transitions: a move of the status is one
        kind of fact, whatever it moves to.

        Raises:
            OrderStatusTransitionError: the move is not in the table.
        """
        old_status = self.status
        self._transition_to(status)
        self._record(
            OrderStatusChanged(
                order_id=self.id,
                order_number=str(self.number),
                customer_id=self.customer_id,
                old_status=old_status.value,
                new_status=status.value,
                reason=None if reason is None else str(reason),
            ),
        )

    def _transition_to(self, status: OrderStatus) -> None:
        """The only place that reads the transition table.

        Raises:
            OrderStatusTransitionError: the move is not in the table.
        """
        if status not in ALLOWED_ORDER_TRANSITIONS[self.status]:
            msg = (
                f"Order '{self.number}' cannot move from "
                f"{self.status.value} to {status.value}."
            )
            raise OrderStatusTransitionError(msg)

        self.status = status
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def _record(self, event: Event) -> None:
        self.events_collection.add_event(event)
