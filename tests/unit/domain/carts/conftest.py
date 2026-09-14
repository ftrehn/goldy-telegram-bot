import pytest

from goldy.domain.carts.factories.cart_factory import CartFactory
from goldy.domain.common.events_collection import EventsCollection
from tests.unit.factories.domain_factories import make_events_collection
from tests.unit.stubs.generators import StubCartIdGenerator


@pytest.fixture()
def events_collection() -> EventsCollection:
    return make_events_collection()


@pytest.fixture()
def cart_factory(events_collection: EventsCollection) -> CartFactory:
    return CartFactory(events_collection, StubCartIdGenerator())
