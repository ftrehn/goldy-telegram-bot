from typing import Final
from urllib.parse import urlsplit

from goldy.setup.bootstrap.loaders.consts import TELEGRAM_PROXY_SCHEMES

TELEGRAM_PROXY_URL_ERROR: Final[str] = (
    "TELEGRAM_PROXY_URL must be a proxy URL with a host and a port, like "
    "socks5://proxy.internal:1080 with user:password@ in front of the host if the "
    f"proxy wants credentials (schemes: {', '.join(sorted(TELEGRAM_PROXY_SCHEMES))}), "
    "or be left unset"
)
"""One message for both loaders that read the variable, so they cannot drift apart.

The example is spelled with the credentials beside the URL rather than inside
it because the secrets scanner in the pre-commit hooks reads ``://a:b@`` as a
committed password, and an exemption comment is a worse fix than a sentence.
"""


def is_telegram_proxy_url(value: str | None) -> bool:
    """Whether ``value`` is a proxy URL the Bot API session can be built on.

    Shared by the bot's loader and the worker's, because both read the same
    variable and an operator must get the same answer from either process.

    Unset is fine — that is the direct route. Set, the URL needs a scheme from
    :data:`TELEGRAM_PROXY_SCHEMES`, a host and a port: ``aiohttp-socks`` refuses
    a URL missing any of the three, and it does so inside ``AiohttpSession``'s
    constructor with a message that names none of our variables. Checking here
    turns that into a startup failure the person deploying can act on.

    Credentials are not inspected. A password with ``@`` or ``/`` in it has to
    be percent-encoded to survive ``urlsplit`` at all, and that is the same
    parser the library uses — so what passes here is what it will read.
    """
    if value is None:
        return True

    parts = urlsplit(value)

    if parts.scheme not in TELEGRAM_PROXY_SCHEMES or not parts.hostname:
        return False

    try:
        port = parts.port
    except ValueError:
        return False

    return port is not None
