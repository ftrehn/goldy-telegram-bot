import logging
from datetime import timedelta
from typing import Final, override

from goldy.application.commands.site.hand_over_order.command import (
    HandOverOrderCommand,
    HandoverOutcome,
)
from goldy.application.common.events import OrderHandoverRejected
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.common.ports.site import (
    HandoverState,
    OrderHandoverDao,
    SiteOrderItem,
    SiteOrderSubmission,
    SiteOrders,
)
from goldy.application.common.ports.users import SiteLinkQueryGateway
from goldy.application.common.views.order import OrderView
from goldy.application.error import (
    SiteCustomerNotLinkedError,
    SiteOrderRejectedError,
    SiteUnavailableError,
)
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)

MAX_RETRY_DELAY: Final[timedelta] = timedelta(hours=1)


def retry_delay(attempts: int) -> timedelta:
    """One minute, then two, four, eight — never more than an hour apart.

    ``attempts`` is how many were made before this failure. The site being
    down for a minute costs a minute; down for a day costs one attempt an
    hour, not a thousand requests against a site that is trying to come back.
    """
    return min(timedelta(minutes=2 ** min(attempts, 10)), MAX_RETRY_DELAY)


class HandOverOrderHandler(CommandHandler[HandOverOrderCommand, HandoverOutcome]):
    """Sends one order to the site and records what the site said (ADR-0004).

    The handover row is locked first and held until the transaction ends, so
    the customer cancelling the same order waits for this to finish and then
    sees the outcome — never an order handed over in the moment it was
    withdrawn.

    The order goes with the prices the customer agreed to: the snapshot on its
    lines. For a customer linked to the site those are the site's own personal
    prices from checkout, and the order lands on their site account; for
    anybody else it goes as a guest's order at retail. If prices moved in
    between, the site refuses with ``prices_changed``, and that is correct —
    the customer agreed to the numbers they saw.

    Three outcomes of a request, three records. An outage is retried later
    with a growing delay and nothing raised, so the retry mark commits. A
    refusal is final: the same order would get the same answer, so it is
    recorded with the site's code and announced to staff through
    ``OrderHandoverRejected``. Anything else — a bad token, a missing scope —
    is configuration, and it raises so the task fails loudly.
    """

    def __init__(
        self,
        order_handover_dao: OrderHandoverDao,
        order_query_gateway: OrderQueryGateway,
        site_link_query_gateway: SiteLinkQueryGateway,
        site_orders: SiteOrders,
        events_collection: EventsCollection,
    ) -> None:
        self._order_handover_dao: Final[OrderHandoverDao] = order_handover_dao
        self._order_query_gateway: Final[OrderQueryGateway] = order_query_gateway
        self._site_link_query_gateway: Final[SiteLinkQueryGateway] = (
            site_link_query_gateway
        )
        self._site_orders: Final[SiteOrders] = site_orders
        self._events_collection: Final[EventsCollection] = events_collection

    @override
    async def handle(self, command: HandOverOrderCommand) -> HandoverOutcome:
        order_id = OrderId(command.order_id)
        handover = await self._order_handover_dao.lock(order_id)

        if handover is None or handover.state is not HandoverState.PENDING:
            return HandoverOutcome.SKIPPED

        order = await self._order_query_gateway.read_by_id(order_id)

        if order is None or order.status == OrderStatus.CANCELLED.value:
            await self._order_handover_dao.mark_withdrawn(order_id)
            return HandoverOutcome.WITHDRAWN

        try:
            status = await self._site_orders.submit(await self._submission(order))
        except SiteUnavailableError as e:
            delay = retry_delay(handover.attempts)
            logger.warning(
                "site handover: order %s not sent, next attempt in %s: %s",
                order.number,
                delay,
                e,
            )
            await self._order_handover_dao.mark_retry(order_id, delay, str(e))
            return HandoverOutcome.RETRY
        except (SiteOrderRejectedError, SiteCustomerNotLinkedError) as e:
            code = (
                e.code if isinstance(e, SiteOrderRejectedError) else "customer_not_linked"
            )
            logger.warning("site handover: order %s refused: %s", order.number, code)
            await self._order_handover_dao.mark_rejected(order_id, code, str(e))
            self._events_collection.add_event(
                OrderHandoverRejected(
                    order_id=order.id,
                    order_number=order.number,
                    code=code,
                ),
            )
            return HandoverOutcome.REJECTED

        await self._order_handover_dao.mark_accepted(order_id, status)
        logger.info(
            "site handover: order %s is site order %s (%s)",
            order.number,
            status.number,
            status.status_name,
        )
        return HandoverOutcome.ACCEPTED

    async def _submission(self, order: OrderView) -> SiteOrderSubmission:
        """The order in the site's shape, on the customer's site account if linked."""
        linked = await self._site_link_query_gateway.read_for(UserId(order.customer_id))
        recipient = " ".join(
            part
            for part in (order.recipient_first_name, order.recipient_last_name)
            if part
        )
        return SiteOrderSubmission(
            external_id=str(order.id),
            number=order.number,
            subject=None if linked is None else str(order.customer_id),
            items=[
                SiteOrderItem(
                    product_id=ProductId(value=line.product_id),
                    quantity=line.quantity,
                    unit_price=line.unit_price.amount,
                )
                for line in order.lines
            ],
            expected_total=order.total.amount,
            recipient_name=recipient,
            recipient_phone=order.recipient_phone_number,
            address=order.delivery_address,
            comment=order.comment,
        )
