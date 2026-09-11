import logging
from collections.abc import Awaitable, Callable
from typing import Any, Final, final, override

from aiogram import BaseMiddleware, Bot
from aiogram.filters import CommandStart
from aiogram.types import (
    TelegramObject,
    Update,
    User as TelegramUser,
)
from aiogram_i18n.cores import BaseCore
from dishka import AsyncContainer

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.views.user import UserView
from goldy.application.error import AuthenticationError
from goldy.domain.common.error import AppError
from goldy.domain.users.values.locale import Locale
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.keyboards import share_phone_keyboard
from goldy.presentation.telegram.common.replying import answer_update

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

    Blocked people are stopped in the same place, and this is the only place
    that stops them: ``User.ensure_active`` exists on the aggregate but nothing
    in the application layer calls it, so an update that got past this gate
    would be served. Enforcing it here rather than in fifteen handlers is the
    decision; the cost is that a second front end has to repeat the gate, which
    is why it lives in a middleware every router inherits rather than in a
    filter somebody has to remember.

    Resolving the user twice, through ``IdentityProvider`` and then the query
    gateway, is deliberate: the first is the port every layer already uses to
    answer "who is this", and the second returns the view the locale manager,
    the staff filter and the handlers all read. Both hit the same request-scoped
    session, and the read side is the natural place for a cache when the second
    lookup starts to matter.

    Renders its messages straight from the Fluent core rather than through
    ``I18nContext``: this runs before the i18n middleware, because that one
    needs the user this one loads in order to pick the right language. For the
    same reason it handles its own failures — an ``AppError`` raised while
    loading the user would otherwise reach an error handler that has no context
    to render with, and the person would get nothing at all.
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
        if not isinstance(event, Update):
            return await handler(event, data)

        event_from_user: TelegramUser | None = data.get("event_from_user")
        locale = Locale.from_language_code(
            event_from_user.language_code if event_from_user is not None else None,
        )

        container: AsyncContainer = data["dishka_container"]

        try:
            user = await self._load_user(container)
        except AppError:
            logger.exception("auth: could not load the user")
            await self._refuse(event, locale, key=text_keys.ERROR_UNKNOWN)
            return None

        data[USER_KEY] = user

        if user is not None and user.is_blocked:
            logger.info("auth: refused blocked user %s", user.id)
            await self._refuse(event, locale, key=text_keys.ERROR_BLOCKED)
            return None

        if user is None and not await _is_registration_step(event, data["bot"]):
            await self._refuse(
                event,
                locale,
                key=text_keys.AUTH_REGISTRATION_REQUIRED,
            )
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
                self._core.get(text_keys.AUTH_SHARE_PHONE_BUTTON, locale.value),
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
