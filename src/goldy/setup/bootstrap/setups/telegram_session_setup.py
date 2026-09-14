import logging
from typing import Final
from urllib.parse import urlsplit

from aiogram.client.session.aiohttp import AiohttpSession

logger: Final[logging.Logger] = logging.getLogger(__name__)


def make_telegram_session(proxy_url: str | None) -> AiohttpSession | None:
    """The transport a ``Bot`` talks to Telegram over, when it is not the default.

    ``None`` when no proxy is configured, and the ``Bot`` builds its own plain
    session — the same object this would return with no proxy on it, so there
    is no reason to construct one here and own a second code path. A URL gets
    an ``AiohttpSession`` whose connector goes through that proxy for every
    request, ``getUpdates`` and ``sendMessage`` alike.

    Takes the URL rather than a config because two configs carry one: the
    bot's :class:`TelegramConfig` and the worker's :class:`NotificationConfig`
    both read ``TELEGRAM_PROXY_URL``, and the two processes have to leave
    through the same door. Its own module rather than a line in
    ``telegram_setup`` for the same reason — that module pulls in the routers
    and the dialogs, which the worker has no business importing.

    The log line names the scheme, the host and the port, and nothing else.
    The URL carries the proxy's password, and a startup log is the first thing
    pasted into a chat when something does not come up.
    """
    if proxy_url is None:
        return None

    parts = urlsplit(proxy_url)
    logger.info(
        "telegram: bot api requests go through a %s proxy at %s:%s",
        parts.scheme,
        parts.hostname,
        parts.port,
    )

    return AiohttpSession(proxy=proxy_url)
