import logging
from collections.abc import Awaitable, Callable
from typing import Any, Final, final, override

from aiogram import Bot, BaseMiddleware
from aiogram.filters import CommandStart
from aiogram.types import TelegramObject, Update
from aiogram.types import User as TelegramUser
from aiogram_i18n.cores import BaseCore
from dishka import AsyncContainer

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.views.user import UserView
from goldy.application.error import AuthenticationError
from goldy.domain.users.values.locale import Locale
from goldy.presentation.telegram.keyboards import share_phone_keyboard
from goldy.presentation.telegram.replying import answer_update

logger: Final[logging.Logger] = logging.getLogger(__name__)

USER_KEY: Final[str] = "user"
"""Where the loaded user is put, and what handlers name in their signature."""

_START: Final[CommandStart] = CommandStart()
"""aiogram's own parser rather than a hand-rolled one.

``/start@goldy_bot`` is what Telegram delivers in a group, and deep links
arrive as ``/start <payload>``. Comparing text to ``"/start"`` gets both wrong,
and getting them wrong here means an unregistered person cannot register.
"""


@final
class AuthMiddleware(BaseMiddleware):
    """Loads the person behind the update, and turns strangers away.

    Fail-closed by construction: anything that is not the registration flow
    itself stops here unless a user was found. A router added later is covered
    without anybody remembering to cover it, which is the whole reason this is a
    middleware and not a filter.

    Blocked people are stopped in the same place. The aggregate refuses them
    too, but only once a command reaches it — and by then they have already been
    shown a menu they cannot use.

    Resolving the user twice, through ``IdentityProvider`` and then the query
    gateway, is deliberate: the first is the port every layer already uses to
    answer "who is this", and the second returns the view the locale manager,
    the staff filter and the handlers all read. Both hit the same request-scoped
    session, and the read side is the natural place for a cache when the second
    lookup starts to matter.

    Renders its one message straight from the Fluent core rather than through
    ``I18nContext``: this runs before the i18n middleware, because that one
    needs the user this one loads in order to pick the right language.
    """

    def __init__(self, core: BaseCore[Any]) -> None:
        self._core: Final[BaseCore[Any]] = core

    @override
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Registered on ``dp.update``, so this is the only shape that arrives.
        if not isinstance(event, Update):
            return await handler(event, data)

        container: AsyncContainer = data["dishka_container"]
        user = await self._load_user(container)
        data[USER_KEY] = user

        # Filled in by aiogram's own context middleware, whichever kind of
        # update this is — which beats digging the sender out of the payload.
        event_from_user: TelegramUser | None = data.get("event_from_user")
        locale = Locale.from_language_code(
            event_from_user.language_code if event_from_user is not None else None,
        )

        if user is not None and user.is_blocked:
            logger.info("auth: refused blocked user %s", user.id)
            await self._refuse(event, locale, key="error-blocked")
            return None

        if user is None and not await _is_registration_step(event, data["bot"]):
            await self._refuse(event, locale, key="auth-registration-required")
            return None

        return await handler(event, data)

    async def _load_user(self, container: AsyncContainer) -> UserView | None:
        identity_provider = await container.get(IdentityProvider)

        try:
            user_id = await identity_provider.get_current_user_id()
        except AuthenticationError:
            return None

        user_query_gateway: UserQueryGateway = await container.get(UserQueryGateway)
        view: UserView | None = await user_query_gateway.read_by_id(user_id)
        return view

    async def _refuse(self, update: Update, locale: Locale, *, key: str) -> None:
        await answer_update(
            update,
            self._core.get(key, locale.value),
            reply_markup=share_phone_keyboard(
                self._core.get("auth-share-phone-button", locale.value),
            ),
        )


async def _is_registration_step(update: Update, bot: Bot) -> bool:
    """Whether this update is one an unregistered person is allowed to send.

    Deliberately narrow: ``/start`` and a shared contact, nothing else.
    Widening it is how a gate stops being one.
    """
    message = update.message

    if message is None:
        return False

    if message.contact is not None:
        return True

    return bool(await _START(message, bot))
