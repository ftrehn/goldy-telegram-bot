from typing import Final, override

from goldy.application.commands.orders.change_delivery_address.command import (
    ChangeDeliveryAddressCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.error import OrderNotFoundError
from goldy.domain.orders.services.authorization.permission import (
    IsOrderOwner,
    OrderAccessContext,
)
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.services.access_service import AccessService


class ChangeDeliveryAddressHandler(CommandHandler[ChangeDeliveryAddressCommand, None]):
    """Corrects where a placed order is going.

    The buyer's own command, so ``IsOrderOwner`` alone: a manager who has to
    redirect a parcel does it by phone, and giving staff a second path here
    would mean a second set of rules about when an address may change.

    How late it may change is the aggregate's business —
    ``EDITABLE_ORDER_STATUSES`` — because once the parcel has left, the address
    on it is settled whoever asks.
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
    async def handle(self, command: ChangeDeliveryAddressCommand) -> None:
        """Rewrites the address, if the order is still going anywhere.

        Raises:
            OrderNotFoundError: no such order.
            AuthorizationError: the order belongs to somebody else.
            OrderNotEditableError: the order has shipped or is finished.
            DomainFieldError: the new address is not one an order can carry.
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

        order.change_delivery_address(DeliveryAddress(value=command.delivery_address))
