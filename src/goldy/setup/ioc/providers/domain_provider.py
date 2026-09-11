from collections import deque
from typing import Final

from dishka import Provider, Scope

from goldy.domain.carts.factories.cart_factory import CartFactory
from goldy.domain.carts.ports.id_generator import CartIdGenerator
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.ports.id_generator import OrderIdGenerator
from goldy.domain.orders.ports.number_generator import OrderNumberGenerator
from goldy.domain.orders.services.checkout_service import CheckoutService
from goldy.domain.users.factories.user_factory import UserFactory
from goldy.domain.users.ports.id_generator import UserIdGenerator
from goldy.domain.users.services.access_service import AccessService
from goldy.infrastructure.adapters.common.uuid7_cart_id_generator import (
    Uuid7CartIdGenerator,
)
from goldy.infrastructure.adapters.common.uuid7_order_id_generator import (
    Uuid7OrderIdGenerator,
)
from goldy.infrastructure.adapters.common.uuid7_user_id_generator import (
    Uuid7UserIdGenerator,
)
from goldy.infrastructure.adapters.persistence.postgres_order_number_generator import (
    PostgresOrderNumberGenerator,
)


def make_events_collection() -> EventsCollection:
    return EventsCollection(events=deque())


def domain_provider() -> Provider:
    """Domain factories, id generators and stateless domain services.

    ``EventsCollection`` is the one that matters: request-scoped, so the
    aggregates a handler touches and the pipeline that drains them are looking
    at the same deque. Process-wide, one request would publish another's events.

    ``AccessService`` holds nothing and could be a singleton; it is resolved per
    request with the rest because building it costs nothing.

    ``CheckoutService`` and ``CartFactory`` are here rather than in the
    interactive group even though only a person ever triggers them: both are
    domain objects built from generators and the events collection, and nothing
    in them knows who is acting. Keeping them in the core is also what keeps
    the rule that every domain service resolves in the worker container - the
    day one of them stops resolving there, something aiogram-shaped has crept
    into the domain.

    ``OrderNumberGenerator`` is the odd one: its adapter draws ``nextval`` from
    a Postgres sequence and therefore asks for the session, which makes it look
    like a gateway. It is bound here anyway, beside the two id generators,
    because what the domain asked for is the same thing in all three cases -
    somewhere for an identifier to come from - and splitting one of them out on
    the strength of how its adapter is implemented would put the answer to "who
    mints an order number" in a second file.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(make_events_collection, provides=EventsCollection)
    provider.provide(source=Uuid7UserIdGenerator, provides=UserIdGenerator)
    provider.provide(source=Uuid7CartIdGenerator, provides=CartIdGenerator)
    provider.provide(source=Uuid7OrderIdGenerator, provides=OrderIdGenerator)
    provider.provide(
        source=PostgresOrderNumberGenerator,
        provides=OrderNumberGenerator,
    )
    provider.provide(source=UserFactory)
    provider.provide(source=CartFactory)
    provider.provide(source=CheckoutService)
    provider.provide(source=AccessService)
    return provider
