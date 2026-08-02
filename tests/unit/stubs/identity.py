"""Stand-ins for the ports that reach outside the process."""

from collections.abc import Iterator
from typing import Final, final, override
from uuid import UUID

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.error import AuthenticationError
from goldy.domain.users.ports.id_generator import UserIdGenerator
from goldy.domain.users.values.user_id import UserId


@final
class StubUserIdGenerator(UserIdGenerator):
    """Hands out ids a test chose in advance.

    Deterministic on purpose: an assertion about which user was created is only
    readable if the test already knows the id.
    """

    def __init__(self, *user_ids: UserId) -> None:
        self._user_ids: Final[Iterator[UserId]] = iter(user_ids)

    @override
    def __call__(self) -> UserId:
        return next(self._user_ids)


@final
class StubIdentityProvider(IdentityProvider):
    """Says who is running the command, without an update to read it from."""

    def __init__(self, user_id: UserId | None = None) -> None:
        self.user_id: UserId | None = user_id

    @override
    async def get_current_user_id(self) -> UserId:
        if self.user_id is None:
            msg = "No user is linked to this account."
            raise AuthenticationError(msg)

        return self.user_id


def sequential_user_ids(count: int) -> tuple[UserId, ...]:
    """``count`` distinct ids, readable at a glance in a failure message."""
    return tuple(
        UserId(UUID(f"{index:08d}-0000-0000-0000-000000000000"))
        for index in range(1, count + 1)
    )
