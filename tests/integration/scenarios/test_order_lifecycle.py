"""What may still be done to an order, and until when.

Two rules live in the aggregate and are stated nowhere else: a customer may take
back an order the shop has not dispatched, and an address may be corrected while
the parcel is still in the shop. Both are also *printed* — ``is_cancellable``
and ``is_editable`` come off the order card and decide which buttons a screen
draws — and the failure worth catching is the two disagreeing, a button offered
for something the aggregate then refuses.
"""

from uuid import UUID

import pytest

from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.commands.orders.change_delivery_address.command import (
    ChangeDeliveryAddressCommand,
)
from goldy.application.commands.orders.change_order_status.command import (
    ChangeOrderStatusCommand,
)
from goldy.application.queries.orders.get_last_delivery_address.query import (
    GetLastDeliveryAddressQuery,
)
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.domain.orders.errors import (
    CustomerCannotCancelProcessedOrderError,
    OrderNotEditableError,
    OrderStatusTransitionError,
    TooShortDeliveryAddressError,
)
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.order_status import OrderStatus
from tests.integration.scenarios.acting import (
    ActingSender,
    CatalogPublisher,
    ManagerRegistrar,
    OrderPlacer,
    ShopperRegistrar,
)
from tests.integration.scenarios.shop import a_shop
from tests.integration.telegram.personas import Person
from tests.unit.factories.shop_factories import DELIVERY_ADDRESS

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

ANOTHER_ADDRESS: str = "Санкт-Петербург, Невский проспект 28, кв. 3"
NOT_AN_ADDRESS: str = "Дома"


async def test_a_customer_takes_back_an_order_the_shop_has_not_sent(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """Cancelling their own order, with nobody owed an explanation.

    No reason is recorded, and that asymmetry is the whole reason cancelling is
    two commands: somebody withdrawing their own order owes nobody a reason,
    while a manager cancelling somebody else's does.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    placed = await place_order(customer)

    before = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert before.is_cancellable is True

    await act(customer, CancelOrderCommand(order_id=placed.order_id))

    after = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert after.status == OrderStatus.CANCELLED.value
    assert after.cancelled_by == CancellationInitiator.CUSTOMER.value
    assert after.cancellation_reason is None
    assert after.is_terminal is True
    assert after.is_cancellable is False


async def test_a_customer_cannot_take_back_an_order_already_on_its_way(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    register_manager: ManagerRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """After dispatch what the customer wants is a return, and returns are not here.

    The card stops offering the button at the same moment the aggregate stops
    accepting the command, which is the pair this asserts — both read
    ``CUSTOMER_CANCELLABLE_STATUSES`` rather than each describing the rule.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    manager = await register_manager()
    placed = await place_order(customer)

    await _move(act, manager, placed.order_id, OrderStatus.CONFIRMED)

    confirmed = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert confirmed.is_cancellable is True

    await _move(act, manager, placed.order_id, OrderStatus.SHIPPED)

    shipped = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert shipped.is_cancellable is False

    with pytest.raises(CustomerCannotCancelProcessedOrderError):
        await act(customer, CancelOrderCommand(order_id=placed.order_id))

    assert (
        await act(customer, GetOrderQuery(order_id=placed.order_id))
    ).status == OrderStatus.SHIPPED.value


async def test_a_customer_corrects_the_address_while_the_parcel_is_in_the_shop(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    register_manager: ManagerRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """The one thing about a placed order that may still be edited.

    Still editable after confirmation, because confirmation means the order was
    accepted for picking and not that it has left; refused once it has shipped,
    because the address on the parcel is already printed and changing the row
    would only make the two disagree.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    manager = await register_manager()
    placed = await place_order(customer)

    await act(
        customer,
        ChangeDeliveryAddressCommand(
            order_id=placed.order_id,
            delivery_address=ANOTHER_ADDRESS,
        ),
    )

    corrected = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert corrected.delivery_address == ANOTHER_ADDRESS
    assert corrected.is_editable is True

    await _move(act, manager, placed.order_id, OrderStatus.CONFIRMED)
    await act(
        customer,
        ChangeDeliveryAddressCommand(
            order_id=placed.order_id,
            delivery_address=DELIVERY_ADDRESS,
        ),
    )
    assert (
        await act(customer, GetOrderQuery(order_id=placed.order_id))
    ).delivery_address == DELIVERY_ADDRESS

    await _move(act, manager, placed.order_id, OrderStatus.SHIPPED)

    shipped = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert shipped.is_editable is False

    with pytest.raises(OrderNotEditableError):
        await act(
            customer,
            ChangeDeliveryAddressCommand(
                order_id=placed.order_id,
                delivery_address=ANOTHER_ADDRESS,
            ),
        )


async def test_an_address_too_short_to_deliver_to_is_refused(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """A word is not an address, and the order keeps the one it had.

    The refusal comes out of the value object rather than out of the handler,
    which is what makes it identical at checkout and at correction — and the
    transaction rolls back, so a refused correction leaves nothing behind.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    placed = await place_order(customer)

    with pytest.raises(TooShortDeliveryAddressError):
        await act(
            customer,
            ChangeDeliveryAddressCommand(
                order_id=placed.order_id,
                delivery_address=NOT_AN_ADDRESS,
            ),
        )

    kept = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert kept.delivery_address == DELIVERY_ADDRESS


async def test_a_finished_order_moves_nowhere(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    register_manager: ManagerRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """Terminality falls out of the transition table, not out of a second check."""
    await publish_catalog(a_shop())
    customer = await register_shopper()
    manager = await register_manager()
    placed = await place_order(customer)

    for status in (OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.COMPLETED):
        await _move(act, manager, placed.order_id, status)

    completed = await act(manager, GetOrderQuery(order_id=placed.order_id))
    assert completed.is_terminal is True
    assert completed.is_cancellable is False

    with pytest.raises(OrderStatusTransitionError):
        await _move(act, manager, placed.order_id, OrderStatus.CONFIRMED)

    with pytest.raises(CustomerCannotCancelProcessedOrderError):
        await act(customer, CancelOrderCommand(order_id=placed.order_id))


async def test_the_next_order_is_offered_the_address_the_last_one_went_to(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """A returning customer types their address once, not every time.

    ``None`` for somebody ordering for the first time is the ordinary answer
    and not a failure — the address screen simply draws no button.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    assert await act(customer, GetLastDeliveryAddressQuery()) is None

    placed = await place_order(customer)
    await act(
        customer,
        ChangeDeliveryAddressCommand(
            order_id=placed.order_id,
            delivery_address=ANOTHER_ADDRESS,
        ),
    )

    assert await act(customer, GetLastDeliveryAddressQuery()) == ANOTHER_ADDRESS


async def _move(
    act: ActingSender,
    manager: Person,
    order_id: UUID,
    status: OrderStatus,
) -> None:
    """One move along the lifecycle, on behalf of staff."""
    await act(manager, ChangeOrderStatusCommand(order_id=order_id, status=status))
