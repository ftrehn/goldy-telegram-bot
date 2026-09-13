"""Assembles the receiver's aiohttp application around a built container.

The container is a parameter and not something built here, for the reason
every adapter takes its collaborators in the constructor: infrastructure must
not import ``setup``. The entry point builds the container it means to serve
with, hands it in, and remains the one that closes it.
"""

from typing import Final

from aiohttp import web
from dishka import AsyncContainer
from dishka.integrations.aiohttp import setup_dishka

from goldy.infrastructure.catalog_receiver.auth import (
    EXPECTED_TOKEN,
    require_bearer_token,
)
from goldy.infrastructure.catalog_receiver.errors import translate_errors
from goldy.infrastructure.catalog_receiver.handlers import ROUTES


def create_catalog_receiver_app(
    container: AsyncContainer,
    *,
    token: str,
    max_body_bytes: int,
) -> web.Application:
    """The application that serves the three catalog routes.

    The middlewares are listed outermost first, and the order is the security
    of the thing. Error translation wraps everything, so that whatever fails
    below it — the token check included — still answers in the JSON the 1C
    module reads. The token check comes next and ahead of the dishka
    middleware ``setup_dishka`` appends after it, so a request without the
    token opens no request scope: no session, no transaction, no cost.

    ``max_body_bytes`` becomes aiohttp's ``client_max_size``, which is
    enforced where the body is read; a batch over it is refused with aiohttp's
    own ``413`` before the mapper sees a byte of it.

    The container is not finalised by the app on shutdown, although the
    integration offers to. The process that built it closes it in its own
    ``finally``, the way the seeder and the worker close theirs, and a second
    close from the app would only make the order of the two a question.

    The token is stripped before it is kept, the way the presented one is
    stripped before it is compared and the way the 1C module trims its own
    constant. The loader measures the token's length after stripping too, so
    a value with a space on either side passes startup; kept raw, it would
    then fail every comparison with nothing in the log to say why.
    """
    app: Final[web.Application] = web.Application(
        client_max_size=max_body_bytes,
        middlewares=[translate_errors, require_bearer_token],
    )
    app[EXPECTED_TOKEN] = token.strip().encode("utf-8")
    app.add_routes(ROUTES)

    setup_dishka(container, app=app, finalize_container=False)

    return app
