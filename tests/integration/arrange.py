"""Signatures of the arrangement fixtures.

Kept beside them rather than inside ``conftest.py`` so a test can name the type
it depends on without importing a conftest, which pytest owns.
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from dishka import AsyncContainer

from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.outbox import OutboxMessage
from goldy.application.common.services.cart_provider import CartProvider
from goldy.domain.carts.factories.cart_factory import CartFactory
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.user_id import UserId
from tests.unit.stubs.identity import StubIdentityProvider

type OutboxSeeder = Callable[[int], Awaitable[list[OutboxMessage]]]
type UserSeeder = Callable[..., Awaitable[User]]
type UserBlocker = Callable[[UserId, str], Awaitable[None]]
"""Takes an id rather than an aggregate: the caller may be holding a persona.

The two are the same person, and a fixture that insisted on the ``User`` would
make every Telegram test reach for one it has no other use for.
"""


class CommandSender(Protocol):
    """Dispatches one request through the mediator, in a scope of its own."""

    async def __call__[TResponse](
        self,
        request: BaseRequest[TResponse],
    ) -> TResponse: ...


async def cart_provider_for(scope: AsyncContainer, user_id: UserId) -> CartProvider:
    """The real ``CartProvider`` over one request scope, acting as ``user_id``.

    Built by hand because the worker container has no ``IdentityProvider`` to
    resolve it with — a background task is nobody's request — while the cart
    tests need the provider's decision, not only the gateway: it is the
    provider that starts a cart on first use and hands the loser of a race the
    cart that won.
    """
    return CartProvider(
        StubIdentityProvider(user_id),
        await scope.get(CartCommandGateway),
        await scope.get(CartFactory),
        await scope.get(EventsCollection),
    )
