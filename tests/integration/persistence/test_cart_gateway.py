"""The ``Cart`` aggregate against a real database, through its port.

Two things are checked here and neither can be checked without Postgres. The
lines are an imperatively mapped child table whose quantity and product id both
arrive through type decorators, so a round trip is the only thing that shows
they come back as the values they went in as.

The other is "one cart per person". That rule spans two aggregates, so the
domain cannot hold it and a read-before-write loses to a concurrent request:
the unique index on ``carts.user_id`` is what actually holds it, the gateway
reports the refused insert as ``CartAlreadyExistsError`` without poisoning the
session, and ``CartProvider`` is written so that the loser of the race is
handed the winner's cart rather than an error to retry.
"""

import asyncio

import pytest
from dishka import AsyncContainer, Scope

from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.transaction_manager import TransactionManager
from goldy.application.error import CartAlreadyExistsError
from goldy.domain.carts.factories.cart_factory import CartFactory
from goldy.domain.carts.values.cart_id import CartId
from goldy.domain.users.values.user_id import UserId
from tests.integration.arrange import UserSeeder, cart_provider_for
from tests.unit.factories.shop_factories import make_product_id, make_quantity

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]


async def test_a_cart_reads_back_with_the_lines_it_was_given(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """Different quantities on purpose — equal ones hide a swapped row."""
    seeded = await seed_user()

    async with worker_container(scope=Scope.REQUEST) as writer:
        cart = await (await cart_provider_for(writer, seeded.id)).current_or_new()
        cart.add_item(make_product_id(1), make_quantity(3))
        cart.add_item(make_product_id(2), make_quantity(7))
        await (await writer.get(TransactionManager)).commit()

    async with worker_container(scope=Scope.REQUEST) as reader:
        loaded = await (await reader.get(CartCommandGateway)).by_user_id(seeded.id)

    assert loaded is not None
    assert loaded.user_id == seeded.id
    assert {line.product_id: line.quantity.value for line in loaded.lines} == {
        make_product_id(1): 3,
        make_product_id(2): 7,
    }


async def test_a_line_removed_from_the_aggregate_leaves_the_table(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The child rows are cascaded by the mapping, not by a delete somebody wrote."""
    seeded = await seed_user()

    async with worker_container(scope=Scope.REQUEST) as writer:
        cart = await (await cart_provider_for(writer, seeded.id)).current_or_new()
        cart.add_item(make_product_id(1), make_quantity(3))
        cart.add_item(make_product_id(2), make_quantity(7))
        await (await writer.get(TransactionManager)).commit()

    async with worker_container(scope=Scope.REQUEST) as editor:
        gateway = await editor.get(CartCommandGateway)
        loaded = await gateway.by_user_id(seeded.id)
        assert loaded is not None
        loaded.remove_item(make_product_id(1))
        await (await editor.get(TransactionManager)).commit()

    async with worker_container(scope=Scope.REQUEST) as reader:
        reloaded = await (await reader.get(CartCommandGateway)).by_user_id(seeded.id)

    assert reloaded is not None
    assert [line.product_id for line in reloaded.lines] == [make_product_id(2)]


async def test_somebody_who_has_never_added_anything_has_no_cart(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The ordinary state of a person who has just registered, and not an error."""
    seeded = await seed_user()

    async with worker_container(scope=Scope.REQUEST) as reader:
        loaded = await (await reader.get(CartCommandGateway)).by_user_id(seeded.id)

    assert loaded is None


async def test_asking_twice_hands_back_the_same_cart(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    seeded = await seed_user()

    async with worker_container(scope=Scope.REQUEST) as first:
        created = await (await cart_provider_for(first, seeded.id)).current_or_new()
        created_id = created.id
        await (await first.get(TransactionManager)).commit()

    async with worker_container(scope=Scope.REQUEST) as second:
        again = await (await cart_provider_for(second, seeded.id)).current_or_new()
        await (await second.get(TransactionManager)).commit()

    assert again.id == created_id


async def test_a_second_cart_for_the_same_person_is_refused_by_the_index(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The gateway reports the clash and leaves the session usable afterwards.

    The read that follows is the point: after a refused insert outside a
    savepoint the session would be rollback-only, and the provider's next move
    — reading the cart that won — would fail with ``PendingRollbackError``.
    """
    seeded = await seed_user()

    async with worker_container(scope=Scope.REQUEST) as first:
        await (await cart_provider_for(first, seeded.id)).current_or_new()
        await (await first.get(TransactionManager)).commit()

    async with worker_container(scope=Scope.REQUEST) as second:
        gateway = await second.get(CartCommandGateway)
        factory = await second.get(CartFactory)

        with pytest.raises(CartAlreadyExistsError):
            await gateway.add(factory.create(seeded.id))

        survivor = await gateway.by_user_id(seeded.id)

    assert survivor is not None


async def test_two_simultaneous_first_additions_land_on_one_cart(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The race the unique index exists for, run for real on two connections.

    Both requests find nothing and both insert. The loser must come back with
    the winner's cart and no error at all, which is ``CartProvider``'s
    decision over the gateway's savepoint.
    """
    seeded = await seed_user()

    first, second = await asyncio.gather(
        _ensure_cart(worker_container, seeded.id),
        _ensure_cart(worker_container, seeded.id),
    )

    async with worker_container(scope=Scope.REQUEST) as reader:
        loaded = await (await reader.get(CartCommandGateway)).by_user_id(seeded.id)

    assert first == second
    assert loaded is not None
    assert loaded.id == first


async def _ensure_cart(container: AsyncContainer, user_id: UserId) -> CartId:
    """One request's worth of "give this person a cart", committed on its own.

    A request scope of its own is what makes this a race rather than two calls
    on one session: each scope resolves its own session and therefore its own
    connection, which is the only way two inserts can meet in the database.
    """
    async with container(scope=Scope.REQUEST) as scope:
        transaction: TransactionManager = await scope.get(TransactionManager)
        cart = await (await cart_provider_for(scope, user_id)).current_or_new()
        await transaction.commit()
        return CartId(cart.id)
