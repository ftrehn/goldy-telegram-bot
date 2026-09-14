"""Who gets a cart, and what happens when two first additions race.

The gateway reports a refused insert and nothing more; the provider is where
"start one on first use" and "take the winner's cart" are decided, and both
decisions are what these tests hold.
"""

import pytest

from goldy.application.common.services.cart_provider import CartProvider
from goldy.application.error import CartNotFoundError
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.carts.factories.cart_factory import CartFactory
from goldy.domain.common.events_collection import EventsCollection
from tests.unit.factories.domain_factories import make_events_collection, make_user_id
from tests.unit.factories.shop_factories import make_cart_id
from tests.unit.stubs.generators import StubCartIdGenerator
from tests.unit.stubs.identity import StubIdentityProvider
from tests.unit.stubs.orders import InMemoryCartCommandGateway
from tests.unit.support import emitted_event_names


@pytest.fixture()
def cart_gateway() -> InMemoryCartCommandGateway:
    return InMemoryCartCommandGateway()


@pytest.fixture()
def cart_provider(
    cart_gateway: InMemoryCartCommandGateway,
    events_collection: EventsCollection,
) -> CartProvider:
    return CartProvider(
        StubIdentityProvider(make_user_id()),
        cart_gateway,
        CartFactory(events_collection, StubCartIdGenerator()),
        events_collection,
    )


async def test_somebody_without_a_cart_gets_one_on_first_use(
    cart_provider: CartProvider,
    cart_gateway: InMemoryCartCommandGateway,
    events_collection: EventsCollection,
) -> None:
    cart = await cart_provider.current_or_new()

    assert cart.user_id == make_user_id()
    assert cart_gateway.carts[make_user_id()] is cart
    assert emitted_event_names(events_collection) == ["CartCreated"]


async def test_asking_again_hands_back_the_same_cart(
    cart_provider: CartProvider,
) -> None:
    first = await cart_provider.current_or_new()

    second = await cart_provider.current_or_new()

    assert second is first


async def test_a_command_that_needs_a_cart_is_refused_when_there_is_none(
    cart_provider: CartProvider,
) -> None:
    """Emptying a cart that never existed must not conjure one up to empty."""
    with pytest.raises(CartNotFoundError):
        await cart_provider.current()


async def test_the_loser_of_a_race_takes_the_winners_cart_without_an_error(
    cart_provider: CartProvider,
    cart_gateway: InMemoryCartCommandGateway,
    events_collection: EventsCollection,
) -> None:
    """The unique index refuses the second insert; the person never notices.

    The ``CartCreated`` the loser recorded is withdrawn too: the cart it
    announces was never written, and an outbox row about it would be a fact
    about nothing.
    """
    winner = Cart.create(
        cart_id=make_cart_id(),
        events_collection=make_events_collection(),
        user_id=make_user_id(),
    )
    cart_gateway.rival = winner

    cart = await cart_provider.current_or_new()

    assert cart is winner
    assert emitted_event_names(events_collection) == []
