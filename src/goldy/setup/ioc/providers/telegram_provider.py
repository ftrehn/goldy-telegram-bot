from typing import Final

from aiogram import Bot
from aiogram.types import User as TelegramUser
from dishka import Provider, Scope, provide
from dishka.integrations.aiogram import AiogramMiddlewareData

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import UserCommandGateway
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.infrastructure.adapters.auth.telegram_identity_provider import (
    TelegramIdentityProvider,
)
from goldy.setup.configs.telegram_config import TelegramConfig


def _sender_account_id(
    middleware_data: AiogramMiddlewareData,
) -> ExternalAccountId | None:
    """The id of whoever sent the update, if it came from a person at all.

    Read from ``event_from_user`` rather than the chat: in a group the chat id
    belongs to the group, and using it would make every member share one
    account.

    A plain function, not a provided dependency: ``ExternalAccountId | None``
    would be a dreadful container key — optional unions are easy to write by
    accident, and the type is a domain value object used all over, so binding it
    globally to "the current Telegram sender" is a trap for the next person.
    """
    event_from_user: TelegramUser | None = middleware_data.get("event_from_user")

    if event_from_user is None:
        return None

    return ExternalAccountId(value=str(event_from_user.id))


class TelegramProvider(Provider):
    """Everything that only exists while a Telegram update is being handled.

    Kept out of the shared providers on purpose: a worker has no
    ``AiogramMiddlewareData``, so an identity bound here simply cannot be
    resolved there. That is the intent — the alternative is a container that
    happily resolves it and fails inside a background task.
    """

    scope = Scope.REQUEST

    @provide(scope=Scope.REQUEST)
    def get_identity_provider(
        self,
        middleware_data: AiogramMiddlewareData,
        user_command_gateway: UserCommandGateway,
    ) -> IdentityProvider:
        return TelegramIdentityProvider(
            _sender_account_id(middleware_data),
            user_command_gateway,
        )


def telegram_context_provider() -> Provider:
    """The bot and its config, both built before the container exists.

    The ``Bot`` in particular: aiogram needs it to construct the dispatcher, so
    it cannot be created by the container that the dispatcher then uses.
    """
    provider: Final[Provider] = Provider(scope=Scope.APP)
    provider.from_context(provides=Bot)
    provider.from_context(provides=TelegramConfig)
    return provider
