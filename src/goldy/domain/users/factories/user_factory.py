import logging
from typing import TYPE_CHECKING, Final, final

from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.entities.messenger_account import MessengerAccount
from goldy.domain.users.entities.user import User
from goldy.domain.users.ports.id_generator import UserIdGenerator

if TYPE_CHECKING:
    from goldy.domain.users.values.external_account_id import ExternalAccountId
    from goldy.domain.users.values.full_name import FullName
    from goldy.domain.users.values.messenger_platform import MessengerPlatform
    from goldy.domain.users.values.messenger_username import MessengerUsername
    from goldy.domain.users.values.phone_number import PhoneNumber

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class UserFactory:
    """Domain factory for the :class:`User` aggregate.

    Exists for one reason: a new user needs an identifier, and the aggregate
    has nowhere to get one. Both the generator and the request-scoped
    ``EventsCollection`` arrive by DI, so the domain never learns how ids are
    produced or where events end up.
    """

    def __init__(
        self,
        events_collection: EventsCollection,
        user_id_generator: UserIdGenerator,
    ) -> None:
        self._events_collection: Final[EventsCollection] = events_collection
        self._user_id_generator: Final[UserIdGenerator] = user_id_generator

    def create(
        self,
        *,
        phone_number: PhoneNumber,
        full_name: FullName,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
        username: MessengerUsername | None = None,
    ) -> User:
        user = User.register(
            user_id=self._user_id_generator(),
            events_collection=self._events_collection,
            phone_number=phone_number,
            full_name=full_name,
            account=MessengerAccount(
                platform=platform,
                external_id=external_id,
                username=username,
            ),
        )
        logger.debug(
            "user_factory: registered %s arriving from %s",
            user.id,
            platform.value,
        )
        return user
