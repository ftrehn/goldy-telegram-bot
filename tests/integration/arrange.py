"""Signatures of the arrangement fixtures.

Kept beside them rather than inside ``conftest.py`` so a test can name the type
it depends on without importing a conftest, which pytest owns.
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.ports.outbox import OutboxMessage
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.user_id import UserId

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
