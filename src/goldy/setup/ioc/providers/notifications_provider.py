from collections.abc import AsyncIterator
from typing import Final

from aiogram import Bot
from dishka import Provider, Scope

from goldy.application.commands.notifications.dispatcher import NotificationDispatcher
from goldy.application.commands.notifications.senders import NotificationSenders
from goldy.application.common.ports.notifications import (
    InboxGateway,
    NotificationRenderer,
    NotificationSender,
)
from goldy.application.common.services.notification_recipient_resolver import (
    NotificationRecipientResolver,
)
from goldy.infrastructure.adapters.notifications.aiogram_notification_sender import (
    AiogramNotificationSender,
)
from goldy.infrastructure.adapters.notifications.fluent_notification_renderer import (
    FluentNotificationRenderer,
)
from goldy.infrastructure.adapters.notifications.notification_locales_path import (
    NOTIFICATION_LOCALES_PATH,
)
from goldy.infrastructure.adapters.notifications.sqlalchemy_inbox_gateway import (
    SqlAlchemyInboxGateway,
)
from goldy.setup.configs.notification_config import NotificationConfig


async def make_notifier_bot(
    notification_config: NotificationConfig,
) -> AsyncIterator[Bot]:
    """The worker's own Bot API client, closed when the container closes.

    A second ``Bot`` rather than the dispatcher's, because these are separate
    processes; what they share is the token, so the notification lands in the
    conversation the customer already has with the shop.

    A generator so the aiohttp session is closed on shutdown. Without it the
    worker leaves a connector open and asyncio complains at exit, which is the
    kind of noise that trains people to ignore shutdown logs.
    """
    bot = Bot(token=notification_config.bot_token)
    try:
        yield bot
    finally:
        await bot.session.close()


def make_notification_renderer() -> NotificationRenderer:
    """Parses the notifier's translations once, when the worker starts.

    The path is resolved by the adapter itself rather than configured, because
    the files ship inside the package next to the code that reads them — a
    setting here would only let a deployment point the worker at translations
    that do not exist.
    """
    return FluentNotificationRenderer(NOTIFICATION_LOCALES_PATH)


def make_notification_senders(sender: NotificationSender) -> NotificationSenders:
    """Every sender this worker holds, which today is the Telegram one.

    MAX will be a second argument here and nothing else: the dispatcher asks
    the registry for the sender behind a person's platform and never learns
    how many there are.
    """
    return NotificationSenders([sender])


def notifications_provider() -> Provider:
    """Everything needed to write to a person, and only the worker gets it.

    Its own group rather than lines added to ``configs_provider`` and
    ``gateways_provider``, and that is the whole reason the bot token stays out
    of the shared core. A container is a statement about what a process may do:
    merging this in would let the bot resolve a notifier, the catalog seeder
    resolve a Bot API client, and a handler that has no business sending
    anything discover at runtime that it can.

    ``APP`` scope for what is expensive to build and belongs to the process —
    the Bot API client with its HTTP session, and the parsed translation files.
    ``REQUEST`` for everything else, the sender included: it holds nothing but
    a reference to the process-wide ``Bot``, so nothing is gained by keeping
    one alive for the lifetime of the worker, and every other collaborator a
    message is handled with lives exactly as long as the message.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.from_context(provides=NotificationConfig, scope=Scope.APP)
    provider.provide(make_notifier_bot, provides=Bot, scope=Scope.APP)
    provider.provide(
        make_notification_renderer,
        provides=NotificationRenderer,
        scope=Scope.APP,
    )
    provider.provide(source=AiogramNotificationSender, provides=NotificationSender)
    provider.provide(make_notification_senders, provides=NotificationSenders)
    provider.provide(source=NotificationRecipientResolver)
    provider.provide(source=SqlAlchemyInboxGateway, provides=InboxGateway)
    provider.provide(source=NotificationDispatcher)
    return provider
