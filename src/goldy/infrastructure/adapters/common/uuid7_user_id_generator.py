from typing import final, override
from uuid import uuid7

from goldy.domain.users.ports.id_generator import UserIdGenerator
from goldy.domain.users.values.user_id import UserId


@final
class Uuid7UserIdGenerator(UserIdGenerator):
    """Mints user ids as UUIDv7.

    Version 7 rather than 4 because this value is the primary key: v7 embeds a
    timestamp in its high bits, so consecutive registrations land next to each
    other in the index instead of scattering writes across every page of the
    B-tree.
    """

    @override
    def __call__(self) -> UserId:
        return UserId(uuid7())
