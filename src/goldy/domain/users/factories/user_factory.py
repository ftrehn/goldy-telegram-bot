import logging
from typing import TYPE_CHECKING, Final, final

from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.entities.user import User
from goldy.domain.users.ports.id_generator import UserIdGenerator

if TYPE_CHECKING:
    from goldy.domain.users.registration import Registration

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

    def create(self, registration: Registration) -> User:
        user = User.register(
            user_id=self._user_id_generator(),
            events_collection=self._events_collection,
            registration=registration,
        )
        logger.debug(
            "user_factory: registered %s arriving from %s",
            user.id,
            registration.account.platform.value,
        )
        return user
