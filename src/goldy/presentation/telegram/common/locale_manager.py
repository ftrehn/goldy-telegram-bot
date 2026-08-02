import logging
from typing import Any, Final, final, override

from aiogram.types import User as TelegramUser
from aiogram_i18n.managers import BaseManager

from goldy.application.common.views.user import UserView
from goldy.domain.users.values.locale import Locale

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class UserLocaleManager(BaseManager):
    """Decides which language to answer an update in.

    Prefers what the person chose and we stored, falling back to what the
    platform reports. The fallback is what serves anyone who has not registered
    yet — and they are precisely the people who most need a comprehensible
    first message.

    Both values come out of the middleware data rather than the database:
    ``user`` was loaded by the auth gate for this very update, and
    ``event_from_user`` is filled in by aiogram's own context middleware for
    every shape of update there is. Querying again just to pick a language
    would double the cost of every message.

    Takes ``**kwargs`` because that is the contract — aiogram-i18n calls this
    with whatever the update happened to put in the data, and which keys are
    present depends on the kind of update.
    """

    @override
    async def get_locale(self, **kwargs: Any) -> str:
        user: UserView | None = kwargs.get("user")

        if user is not None:
            return user.locale

        event_from_user: TelegramUser | None = kwargs.get("event_from_user")
        language_code = (
            event_from_user.language_code if event_from_user is not None else None
        )

        return Locale.from_language_code(language_code).value

    @override
    async def set_locale(self, locale: str, **kwargs: Any) -> None:
        """Not supported: the stored preference is the only source of truth.

        Letting the i18n context change the language would put it out of step
        with the database, and the database is what the worker reads when it
        sends an order update outside of any conversation.
        """
        msg = (
            f"Cannot set locale to {locale!r} here — use ChangeUserLocaleCommand, "
            f"which stores it where every process can see it."
        )
        raise NotImplementedError(msg)
