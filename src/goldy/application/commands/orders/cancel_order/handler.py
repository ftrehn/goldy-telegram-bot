from typing import Final, override

from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.ports.site import (
    HandoverState,
    OrderHandoverDao,
    SiteOrders,
)
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.error import OrderNotFoundError
from goldy.domain.orders.services.authorization.permission import (
    IsOrderOwner,
    OrderAccessContext,
)
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.services.access_service import AccessService


class CancelOrderHandler(CommandHandler[CancelOrderCommand, None]):
    """Lets the buyer withdraw an order the shop has not dispatched yet.

    Authorised by ``IsOrderOwner`` and nothing else. Whether the order is still
    at a stage a customer may withdraw is not asked here either — ``cancel``
    holds that against ``CUSTOMER_CANCELLABLE_STATUSES``, so the rule has one
    home and a manager cancelling through the other command is not subject to
    it. After dispatch what the customer wants is a return, and returns do not
    live in this bot.

    An order already handed over to the site (ADR-0004) is cancelled there
    first, and only if the site agrees is it cancelled here: once a manager
    has taken it into work on the site, the customer cannot withdraw it any
    more, whatever the bot's own status says. An order still waiting in the
    handover queue is simply withdrawn from it. The handover row is locked for
    the length of the transaction, so the order cannot be handed over in the
    moment it is being cancelled.
    """

    def __init__(
        self,
        user_provider: UserProvider,
        access_service: AccessService,
        order_command_gateway: OrderCommandGateway,
        order_handover_dao: OrderHandoverDao,
        site_orders: SiteOrders,
    ) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._access_service: Final[AccessService] = access_service
        self._order_command_gateway: Final[OrderCommandGateway] = order_command_gateway
        self._order_handover_dao: Final[OrderHandoverDao] = order_handover_dao
        self._site_orders: Final[SiteOrders] = site_orders

    @override
    async def handle(self, command: CancelOrderCommand) -> None:
        """Cancels the order on behalf of the person who placed it.

        Raises:
            OrderNotFoundError: no such order.
            AuthorizationError: the order belongs to somebody else.
            CustomerCannotCancelProcessedOrderError: it has already been
                dispatched.
            SiteOrderNotCancellableError: the site has it in work already.
            SiteUnavailableError: it is on the site, and the site did not
                answer — nothing is cancelled anywhere.
        """
        customer = await self._user_provider.current()
        order_id = OrderId(command.order_id)
        order = await self._order_command_gateway.by_id(order_id)

        if order is None:
            msg = f"Order '{order_id}' does not exist."
            raise OrderNotFoundError(msg)

        self._access_service.authorize(
            IsOrderOwner(),
            context=OrderAccessContext(
                subject=customer,
                order_customer_id=order.customer_id,
            ),
        )

        order.cancel(
            initiated_by=CancellationInitiator.CUSTOMER,
            cancelled_by_user_id=customer.id,
        )

        handover = await self._order_handover_dao.lock(order_id)

        if handover is None:
            return

        if handover.state is HandoverState.PENDING:
            await self._order_handover_dao.mark_withdrawn(order_id)
        elif handover.state is HandoverState.ACCEPTED:
            await self._site_orders.cancel(
                str(order_id),
                str(customer.id) if customer.is_site_linked else None,
                None,
            )
