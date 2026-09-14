"""Cancelling, moving the status along, and correcting the address.

Three commands with two different authorisations between them, which is the
point: the buyer and the manager are held to different rules, and the rules
live in permissions and in the transition table rather than in a branch.
"""

from uuid import UUID

import pytest

from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.commands.orders.cancel_order.handler import CancelOrderHandler
from goldy.application.commands.orders.change_delivery_address.command import (
    ChangeDeliveryAddressCommand,
)
from goldy.application.commands.orders.change_delivery_address.handler import (
    ChangeDeliveryAddressHandler,
)
from goldy.application.commands.orders.change_order_status.command import (
    ChangeOrderStatusCommand,
)
from goldy.application.commands.orders.change_order_status.handler import (
    ChangeOrderStatusHandler,
)
from goldy.application.error import OrderNotFoundError
from goldy.domain.orders.errors import (
    CancellationReasonRequiredError,
    CustomerCannotCancelProcessedOrderError,
    OrderNotEditableError,
    OrderStatusTransitionError,
)
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.errors import AuthorizationError
from goldy.domain.users.values.user_role import UserRole
from tests.unit.application.conftest import ActingAs, UserSeeder

from .conftest import OrderSeeder

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}
OTHER_CUSTOMER = {"phone_number": "+79994444444", "external_id": "444"}
MANAGER = {"phone_number": "+79992222222", "external_id": "222"}

NEW_ADDRESS: str = "Санкт-Петербург, Невский 20, кв. 3"
CANCELLATION_REASON: str = "Товара нет на складе"
UNKNOWN_ORDER = UUID(int=999)


async def test_a_customer_cancels_their_own_new_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)

    await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert order.status is OrderStatus.CANCELLED
    assert order.cancelled_by is CancellationInitiator.CUSTOMER
    assert order.cancellation_reason is None


async def test_a_confirmed_order_is_still_the_customers_to_withdraw(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    """Confirmation does not run the buyer out of chances to change their mind.

    It means the shop accepted the order for picking, and nothing more.
    """
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.CONFIRMED)

    await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert order.status is OrderStatus.CANCELLED


async def test_a_customer_cannot_cancel_a_dispatched_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.SHIPPED)

    with pytest.raises(CustomerCannotCancelProcessedOrderError):
        await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert order.status is OrderStatus.SHIPPED


async def test_a_customer_cannot_cancel_somebody_elses_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    owner = await seed_user(**CUSTOMER)
    stranger = await seed_user(**OTHER_CUSTOMER)
    acting_as(stranger.id)
    order = seed_order(owner.id, OrderStatus.NEW)

    with pytest.raises(AuthorizationError):
        await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert order.status is OrderStatus.NEW


async def test_cancelling_an_order_that_does_not_exist(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    with pytest.raises(OrderNotFoundError):
        await cancel_order_handler.handle(CancelOrderCommand(order_id=UNKNOWN_ORDER))


async def test_a_manager_confirms_a_new_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_order_status_handler: ChangeOrderStatusHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    acting_as(manager.id)
    order = seed_order(customer.id, OrderStatus.NEW)

    await change_order_status_handler.handle(
        ChangeOrderStatusCommand(order_id=order.id, status=OrderStatus.CONFIRMED),
    )

    assert order.status is OrderStatus.CONFIRMED


async def test_a_manager_may_cancel_a_dispatched_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_order_status_handler: ChangeOrderStatusHandler,
) -> None:
    """A courier bringing a parcel back is a real move, and only staff make it."""
    customer = await seed_user(**CUSTOMER)
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    acting_as(manager.id)
    order = seed_order(customer.id, OrderStatus.SHIPPED)

    await change_order_status_handler.handle(
        ChangeOrderStatusCommand(
            order_id=order.id,
            status=OrderStatus.CANCELLED,
            reason=CANCELLATION_REASON,
        ),
    )

    assert order.status is OrderStatus.CANCELLED
    assert order.cancelled_by is CancellationInitiator.MANAGER
    assert str(order.cancellation_reason) == CANCELLATION_REASON


async def test_a_manager_cancelling_must_say_why(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_order_status_handler: ChangeOrderStatusHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    acting_as(manager.id)
    order = seed_order(customer.id, OrderStatus.NEW)

    with pytest.raises(CancellationReasonRequiredError):
        await change_order_status_handler.handle(
            ChangeOrderStatusCommand(order_id=order.id, status=OrderStatus.CANCELLED),
        )

    assert order.status is OrderStatus.NEW


async def test_a_move_outside_the_table_is_refused(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_order_status_handler: ChangeOrderStatusHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    acting_as(manager.id)
    order = seed_order(customer.id, OrderStatus.NEW)

    with pytest.raises(OrderStatusTransitionError):
        await change_order_status_handler.handle(
            ChangeOrderStatusCommand(order_id=order.id, status=OrderStatus.SHIPPED),
        )

    assert order.status is OrderStatus.NEW


async def test_an_order_cannot_be_moved_back_to_new(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_order_status_handler: ChangeOrderStatusHandler,
) -> None:
    """Nothing in the transition table leads back to ``NEW``.

    An order that has been confirmed cannot be un-confirmed.
    """
    customer = await seed_user(**CUSTOMER)
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    acting_as(manager.id)
    order = seed_order(customer.id, OrderStatus.CONFIRMED)

    with pytest.raises(OrderStatusTransitionError):
        await change_order_status_handler.handle(
            ChangeOrderStatusCommand(order_id=order.id, status=OrderStatus.NEW),
        )

    assert order.status is OrderStatus.CONFIRMED


async def test_a_customer_cannot_move_their_own_order_along(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_order_status_handler: ChangeOrderStatusHandler,
) -> None:
    """Owning the order buys nothing here — this command is staff only."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)

    with pytest.raises(AuthorizationError):
        await change_order_status_handler.handle(
            ChangeOrderStatusCommand(order_id=order.id, status=OrderStatus.CONFIRMED),
        )

    assert order.status is OrderStatus.NEW


async def test_the_buyer_corrects_the_address_of_a_new_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_delivery_address_handler: ChangeDeliveryAddressHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)

    await change_delivery_address_handler.handle(
        ChangeDeliveryAddressCommand(order_id=order.id, delivery_address=NEW_ADDRESS),
    )

    assert str(order.delivery_address) == NEW_ADDRESS


async def test_the_address_of_a_dispatched_order_is_settled(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_delivery_address_handler: ChangeDeliveryAddressHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.SHIPPED)
    address_before = str(order.delivery_address)

    with pytest.raises(OrderNotEditableError):
        await change_delivery_address_handler.handle(
            ChangeDeliveryAddressCommand(
                order_id=order.id,
                delivery_address=NEW_ADDRESS,
            ),
        )

    assert str(order.delivery_address) == address_before


async def test_a_stranger_cannot_redirect_somebody_elses_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    change_delivery_address_handler: ChangeDeliveryAddressHandler,
) -> None:
    """The one thing between a guessed identifier and a hijacked delivery."""
    owner = await seed_user(**CUSTOMER)
    stranger = await seed_user(**OTHER_CUSTOMER)
    acting_as(stranger.id)
    order = seed_order(owner.id, OrderStatus.NEW)
    address_before = str(order.delivery_address)

    with pytest.raises(AuthorizationError):
        await change_delivery_address_handler.handle(
            ChangeDeliveryAddressCommand(
                order_id=order.id,
                delivery_address=NEW_ADDRESS,
            ),
        )

    assert str(order.delivery_address) == address_before
