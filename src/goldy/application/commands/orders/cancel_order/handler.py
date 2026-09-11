from typing import Final, override

from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.orders import OrderCommandGateway
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
    """

    def __init__(
        self,
        user_provider: UserProvider,
        access_service: AccessService,
        order_command_gateway: OrderCommandGateway,
    ) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._access_service: Final[AccessService] = access_service
        self._order_command_gateway: Final[OrderCommandGateway] = order_command_gateway

    @override
    async def handle(self, command: CancelOrderCommand) -> None:
        """Cancels the order on behalf of the person who placed it.

        Raises:
            OrderNotFoundError: no such order.
            AuthorizationError: the order belongs to somebody else.
            CustomerCannotCancelProcessedOrderError: it has already been
                dispatched.
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

        order.cancel(initiated_by=CancellationInitiator.CUSTOMER)
