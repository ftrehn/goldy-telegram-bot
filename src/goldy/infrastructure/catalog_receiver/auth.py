"""The one gate in front of every route: a shared bearer token.

A shared secret rather than an identity, because the only client is one
scheduled job in one accounting system, and the token is the whole of what it
has to prove. It is compared with ``hmac.compare_digest`` so that the time a
comparison takes says nothing about how many leading bytes were right, and
it is compared as bytes on both sides because ``compare_digest`` refuses to
mix ``str`` with ``bytes`` and a header value is bytes by the time it reaches
this process.

Every refusal is the same ``401`` with the same body. Whether the header was
missing, spelled with another scheme or carried the wrong token is not told
apart in the response, and the comparison runs even when nothing was
presented — a client that could learn which of the three it got wrong would
be a client being taught how to get it right.

Outermost of the receiver's own middlewares and ahead of the dishka one, so
that a request without the token opens no request scope and touches no
database: whatever a stranger can make this process do must cost it nothing.
"""

import hmac
from http import HTTPStatus
from typing import Final

from aiohttp import web
from aiohttp.typedefs import Handler

EXPECTED_TOKEN: Final[web.AppKey[bytes]] = web.AppKey("expected_token", bytes)
"""Where the app keeps the token it accepts, already encoded for the comparison."""


@web.middleware
async def require_bearer_token(
    request: web.Request,
    handler: Handler,
) -> web.StreamResponse:
    if not hmac.compare_digest(_presented_token(request), request.app[EXPECTED_TOKEN]):
        return web.json_response(
            {"error": "unauthorized"},
            status=HTTPStatus.UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await handler(request)


def _presented_token(request: web.Request) -> bytes:
    """The credential of a ``Bearer`` header, or nothing to compare against.

    Encoded with ``surrogateescape`` because that is how aiohttp decoded the
    header: a byte that was not UTF-8 comes back as the byte it was, compares
    unequal and earns its ``401``, instead of raising on the way out and
    earning a ``500``.
    """
    scheme, _, credential = request.headers.get("Authorization", "").partition(" ")

    if scheme.casefold() != "bearer":
        return b""

    return credential.strip().encode("utf-8", "surrogateescape")
