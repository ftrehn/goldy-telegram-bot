from collections import deque
from typing import Final

from dishka import Provider, Scope

from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.factories.user_factory import UserFactory
from goldy.domain.users.ports.id_generator import UserIdGenerator
from goldy.domain.users.services.access_service import AccessService
from goldy.infrastructure.adapters.common.uuid7_user_id_generator import (
    Uuid7UserIdGenerator,
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
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(make_events_collection, provides=EventsCollection)
    provider.provide(source=Uuid7UserIdGenerator, provides=UserIdGenerator)
    provider.provide(source=UserFactory)
    provider.provide(source=AccessService)
    return provider
