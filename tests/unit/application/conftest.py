"""Wiring shared by every application-layer test: ports, stubs, seeding."""

from collections import deque
from collections.abc import Awaitable, Callable

import pytest

from goldy.application.common.ports.mappers import UserViewMapper
from goldy.application.common.services.user_provider import UserProvider
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.entities.user import User
from goldy.domain.users.factories.user_factory import UserFactory
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_role import UserRole
from goldy.infrastructure.mappers.adaptix_user_view_mapper import AdaptixUserViewMapper
from tests.unit.factories.domain_factories import (
    make_external_account_id,
    make_full_name,
    make_phone_number,
)
from tests.unit.stubs.gateways import InMemoryUserCommandGateway
from tests.unit.stubs.identity import (
    StubIdentityProvider,
    StubUserIdGenerator,
    sequential_user_ids,
)

type UserSeeder = Callable[..., Awaitable[User]]
type ActingAs = Callable[[UserId], None]

SEEDED_USER_IDS = sequential_user_ids(10)


@pytest.fixture()
def events_collection() -> EventsCollection:
    """One request-scoped collection, shared by every aggregate in a test."""
    return EventsCollection(events=deque())


@pytest.fixture()
def user_gateway() -> InMemoryUserCommandGateway:
    return InMemoryUserCommandGateway()


@pytest.fixture()
def identity_provider() -> StubIdentityProvider:
    return StubIdentityProvider()


@pytest.fixture()
def user_id_generator() -> StubUserIdGenerator:
    return StubUserIdGenerator(*SEEDED_USER_IDS)


@pytest.fixture()
def user_factory(
    events_collection: EventsCollection,
    user_id_generator: StubUserIdGenerator,
) -> UserFactory:
    return UserFactory(events_collection, user_id_generator)


@pytest.fixture()
def user_provider(
    identity_provider: StubIdentityProvider,
    user_gateway: InMemoryUserCommandGateway,
) -> UserProvider:
    return UserProvider(identity_provider, user_gateway)


@pytest.fixture()
def access_service() -> AccessService:
    return AccessService()


@pytest.fixture()
def user_view_mapper() -> UserViewMapper:
    """The real converter — it is pure, so stubbing it would only hide bugs."""
    return AdaptixUserViewMapper()


@pytest.fixture()
def seed_user(
    user_gateway: InMemoryUserCommandGateway,
    user_factory: UserFactory,
) -> UserSeeder:
    """Puts a user in the gateway the way registration would have."""

    async def seed(
        phone_number: str = "+79991234567",
        external_id: str = "123456",
        role: UserRole = UserRole.CUSTOMER,
    ) -> User:
        user = user_factory.create(
            phone_number=make_phone_number(phone_number),
            full_name=make_full_name(),
            platform=MessengerPlatform.TELEGRAM,
            external_id=make_external_account_id(external_id),
        )
        if role is not UserRole.CUSTOMER:
            user.assign_role(role)
        await user_gateway.add(user)
        return user

    return seed


@pytest.fixture()
def acting_as(identity_provider: StubIdentityProvider) -> ActingAs:
    """Names whoever the next command runs as."""

    def act(user_id: UserId) -> None:
        identity_provider.user_id = user_id

    return act
