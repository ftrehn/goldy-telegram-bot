"""Who may see and move an order, asked of a real order and a real person.

The permissions themselves are unit-tested against constructed aggregates, and
those tests pass whether or not a handler ever calls them. What only a scenario
can ask is whether the caller reaching a command *is* the person the permission
was given — the identity travels from a messenger account through the provider
into ``UserProvider.current()``, and the whole guarantee rests on it arriving
unchanged.

Two of the refusals here are the only thing between a guessed identifier and a
stranger's delivery address, which is the most personal thing this bot stores.
"""

import pytest

from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.commands.orders.change_delivery_address.command import (
    ChangeDeliveryAddressCommand,
)
from goldy.application.commands.orders.change_order_status.command import (
    ChangeOrderStatusCommand,
)
from goldy.application.commands.users.block_user.command import BlockUserCommand
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from goldy.application.queries.orders.list_orders.query import ListOrdersQuery
from goldy.domain.orders.errors import CancellationReasonRequiredError
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.errors import AuthorizationError
from tests.integration.scenarios.acting import (
    ActingSender,
    AdministratorRegistrar,
    CatalogPublisher,
    ManagerRegistrar,
    OrderPlacer,
    ShopperRegistrar,
)
from tests.integration.scenarios.shop import a_shop

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

BLOCK_REASON: str = "Оскорблял поддержку"
CANCELLATION_REASON: str = "Товара не оказалось на складе"


async def test_a_customer_cannot_reach_an_order_that_is_not_theirs(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """Reading it, cancelling it, redirecting it — all four refused the same way.

    Asserted together because they are one rule, ``IsOrderOwner``, reached
    through four different handlers, and a handler that forgot to ask is
    exactly the failure this catches. The identifier is a real one: the point
    is that holding it is not enough.
    """
    await publish_catalog(a_shop())
    buyer = await register_shopper()
    stranger = await register_shopper()

    placed = await place_order(buyer)

    with pytest.raises(AuthorizationError):
        await act(stranger, GetOrderQuery(order_id=placed.order_id))

    with pytest.raises(AuthorizationError):
        await act(stranger, CancelOrderCommand(order_id=placed.order_id))

    with pytest.raises(AuthorizationError):
        await act(
            stranger,
            ChangeDeliveryAddressCommand(
                order_id=placed.order_id,
                delivery_address="Тверь, Советская 12, кв. 7",
            ),
        )

    with pytest.raises(AuthorizationError):
        await act(
            stranger,
            ChangeOrderStatusCommand(
                order_id=placed.order_id,
                status=OrderStatus.CONFIRMED,
            ),
        )

    untouched = await act(buyer, GetOrderQuery(order_id=placed.order_id))
    assert untouched.status == OrderStatus.NEW.value


async def test_a_history_holds_only_its_own_owner_s_orders(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """``ListMyOrdersQuery`` has no field a stranger's id could go into.

    Which is a stronger guarantee than a check, and this asserts the other half
    of it: that the identity it takes instead is the right one.
    """
    await publish_catalog(a_shop())
    first = await register_shopper()
    second = await register_shopper()

    theirs = await place_order(first, {1: 1})
    others = await place_order(second, {2: 2})

    mine = await act(first, ListMyOrdersQuery())
    assert [order.id for order in mine.orders] == [theirs.order_id]
    assert others.order_id not in {order.id for order in mine.orders}


async def test_a_customer_cannot_read_the_queue_the_managers_work_from(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """``IsStaff`` guards the list, because a list has no one order to ask about.

    The queue carries every customer's name, total and address, so this is the
    one refusal whose absence would expose the whole shop at once.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    await place_order(customer)

    with pytest.raises(AuthorizationError):
        await act(customer, ListOrdersQuery())


async def test_a_manager_opens_and_moves_an_order_placed_by_anybody(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    register_manager: ManagerRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """The same card, through the same query, by the other half of one rule."""
    await publish_catalog(a_shop())
    customer = await register_shopper()
    manager = await register_manager()
    placed = await place_order(customer)

    card = await act(manager, GetOrderQuery(order_id=placed.order_id))
    assert card.customer_id == customer.user_id

    await act(
        manager,
        ChangeOrderStatusCommand(
            order_id=placed.order_id,
            status=OrderStatus.CONFIRMED,
        ),
    )

    assert (
        await act(customer, GetOrderQuery(order_id=placed.order_id))
    ).status == OrderStatus.CONFIRMED.value


async def test_a_manager_cancelling_somebody_else_s_order_has_to_say_why(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    register_manager: ManagerRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """The asymmetry the customer's own cancellation does not carry.

    Held by the aggregate rather than by the command, so it cannot be got round
    by reaching the aggregate another way — and the refusal rolls the whole
    transaction back, leaving the order where it was.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    manager = await register_manager()
    placed = await place_order(customer)

    with pytest.raises(CancellationReasonRequiredError):
        await act(
            manager,
            ChangeOrderStatusCommand(
                order_id=placed.order_id,
                status=OrderStatus.CANCELLED,
            ),
        )

    assert (
        await act(manager, GetOrderQuery(order_id=placed.order_id))
    ).status == OrderStatus.NEW.value

    await act(
        manager,
        ChangeOrderStatusCommand(
            order_id=placed.order_id,
            status=OrderStatus.CANCELLED,
            reason=CANCELLATION_REASON,
        ),
    )

    cancelled = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert cancelled.status == OrderStatus.CANCELLED.value
    assert cancelled.cancelled_by == CancellationInitiator.MANAGER.value
    assert cancelled.cancellation_reason == CANCELLATION_REASON


async def test_blocking_a_customer_badges_their_order_without_stopping_it(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    register_administrator: AdministratorRegistrar,
    register_manager: ManagerRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """Blocking is about access, not about obligations.

    An order placed before the block can perfectly well go on to be confirmed —
    the goods were promised — so the queue draws a badge and the manager
    decides. That is the whole of what blocking means to an order, and the
    refusal itself lives one layer up: the auth gate stops a blocked person
    before any handler runs, which is covered in
    ``tests/integration/telegram/test_auth_gate.py``.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    administrator = await register_administrator()
    manager = await register_manager()
    placed = await place_order(customer)

    await act(
        administrator,
        BlockUserCommand(user_id=customer.user_id, reason=BLOCK_REASON),
    )

    queue = await act(manager, ListOrdersQuery())
    [row] = [order for order in queue.orders if order.id == placed.order_id]
    assert row.customer_is_blocked is True

    card = await act(manager, GetOrderQuery(order_id=placed.order_id))
    assert card.customer_is_blocked is True

    await act(
        manager,
        ChangeOrderStatusCommand(
            order_id=placed.order_id,
            status=OrderStatus.CONFIRMED,
        ),
    )

    assert (
        await act(manager, GetOrderQuery(order_id=placed.order_id))
    ).status == OrderStatus.CONFIRMED.value
