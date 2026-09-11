from typing import Final, override

from goldy.application.commands.orders.change_order_status.command import (
    ChangeOrderStatusCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.error import OrderNotFoundError
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.errors import OrderStatusTransitionError
from goldy.domain.orders.services.authorization.permission import (
    CanManageOrders,
    OrderAccessContext,
)
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.services.access_service import AccessService


class ChangeOrderStatusHandler(CommandHandler[ChangeOrderStatusCommand, None]):
    """Moves an order through its lifecycle, on behalf of staff.

    Authorised by ``CanManageOrders``, which does not restate what counts as
    staff but delegates to ``IsStaff``. The rules about the move itself are the
    aggregate's: which transitions exist, that a cancellation by staff needs a
    reason, that a finished order moves nowhere.

    A manager may cancel a dispatched order, and that is deliberate — a courier
    brings a parcel back, which is a real thing that happens. The customer may
    not, and that difference is the whole reason cancelling is two commands.
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
    async def handle(self, command: ChangeOrderStatusCommand) -> None:
        """Applies the move the manager asked for.

        Raises:
            OrderNotFoundError: no such order.
            AuthorizationError: the caller is not staff.
            OrderStatusTransitionError: the move is not in the table.
            CancellationReasonRequiredError: staff cancelled without a reason.
        """
        subject = await self._user_provider.current()
        order_id = OrderId(command.order_id)
        order = await self._order_command_gateway.by_id(order_id)

        if order is None:
            msg = f"Order '{order_id}' does not exist."
            raise OrderNotFoundError(msg)

        self._access_service.authorize(
            CanManageOrders(),
            context=OrderAccessContext(
                subject=subject,
                order_customer_id=order.customer_id,
            ),
        )

        self._move(order, command)

    def _move(self, order: Order, command: ChangeOrderStatusCommand) -> None:
        """Calls the aggregate method that names the move.

        A match over the target rather than a generic "set the status": each
        transition is a method on the aggregate with its own preconditions and
        its own event, and a setter would route around all of them.

        ``NEW`` appears in the match because the enum has five members and is
        refused because nothing in ``ALLOWED_ORDER_TRANSITIONS`` leads back to
        it — an order cannot be un-confirmed.

        Raises:
            OrderStatusTransitionError: the move is not in the table.
            CancellationReasonRequiredError: staff cancelled without a reason.
        """
        match command.status:
            case OrderStatus.CONFIRMED:
                order.confirm()
            case OrderStatus.SHIPPED:
                order.ship()
            case OrderStatus.COMPLETED:
                order.complete()
            case OrderStatus.CANCELLED:
                order.cancel(
                    initiated_by=CancellationInitiator.MANAGER,
                    reason=(
                        None
                        if command.reason is None
                        else CancellationReason(value=command.reason)
                    ),
                )
            case OrderStatus.NEW:
                msg = f"Order '{order.number}' cannot be moved back to new."
                raise OrderStatusTransitionError(msg)
