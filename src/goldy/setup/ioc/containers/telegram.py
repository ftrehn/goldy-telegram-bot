from collections.abc import Iterable
from typing import Final

from dishka import AsyncContainer, Provider, make_async_container
from dishka.integrations.aiogram import AiogramProvider

from goldy.setup.ioc.containers.common import common_providers, interactive_providers
from goldy.setup.ioc.providers import TelegramProvider, telegram_context_provider


def telegram_providers() -> Iterable[Provider]:
    """The shared core plus everything specific to serving Telegram updates."""
    return (
        *common_providers(),
        *interactive_providers(),
        telegram_context_provider(),
        TelegramProvider(),
        AiogramProvider(),
    )


def make_telegram_container(context: dict[type, object]) -> AsyncContainer:
    """Builds the container the bot process runs on.

    *context* carries the objects created before the container exists — the
    loaded configs and the ``Bot`` the dispatcher was built with.
    """
    providers: Final[Iterable[Provider]] = tuple(telegram_providers())
    return make_async_container(*providers, context=context)
