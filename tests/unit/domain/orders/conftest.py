import pytest

from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.services.checkout_service import CheckoutService
from tests.unit.factories.domain_factories import make_events_collection
from tests.unit.stubs.generators import StubOrderIdGenerator


@pytest.fixture()
def events_collection() -> EventsCollection:
    """The request-scoped collection the service and the order it places share."""
    return make_events_collection()


@pytest.fixture()
def checkout_service(events_collection: EventsCollection) -> CheckoutService:
    return CheckoutService(events_collection, StubOrderIdGenerator())
