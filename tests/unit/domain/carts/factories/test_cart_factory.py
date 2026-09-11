from uuid import UUID

from goldy.domain.carts.factories.cart_factory import CartFactory
from tests.unit.factories.domain_factories import make_user_id
from tests.unit.support import emitted_event_names


def test_the_factory_hands_the_new_cart_the_generated_id(
    cart_factory: CartFactory,
) -> None:
    """The only reason the factory exists: the aggregate cannot mint an id."""
    cart = cart_factory.create(make_user_id())

    assert cart.id == UUID(int=1)
    assert cart.user_id == make_user_id()


def test_a_new_cart_starts_empty_and_announces_nothing(
    cart_factory: CartFactory,
) -> None:
    cart = cart_factory.create(make_user_id())

    assert cart.is_empty is True
    assert emitted_event_names(cart.events_collection) == []
