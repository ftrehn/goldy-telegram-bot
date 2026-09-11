from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class NotificationConfig:
    """What the worker needs in order to write to people on its own.

    Separate from :class:`TelegramConfig` even though both hold the same token,
    and the separation is the point. ``TelegramConfig`` says how the *bot*
    process is wired — dialogue storage, event isolation, whether to drop
    pending updates — and none of that means anything in a worker. Handing the
    worker that object would give it settings it cannot act on and, worse,
    would make ``configs_provider`` the place the token lives, where every
    process could reach it.

    Reading the same ``TELEGRAM_BOT_TOKEN`` is deliberate too. The notification
    arrives in the conversation the customer already has with the shop, so it
    has to come from that bot; a second variable holding a copy of the same
    secret is a second thing to rotate and the one that gets forgotten.

    Attributes:
        bot_token: The token from BotFather, the same one the bot answers with.
    """

    bot_token: str
