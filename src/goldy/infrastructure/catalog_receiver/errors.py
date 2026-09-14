"""Turns what a handler raised into the status code and body 1C reads.

The contract with the 1C side is a JSON body of ``{"error": <code>,
"detail": <text>}`` on every failure, and the code is what its scheduled job
branches on: ``bad_request`` means the body it built is wrong and resending
it is pointless, ``snapshot_rejected`` means the batches were fine and the
finalisation was refused, ``internal`` means try again later. The text goes
into the 1C event log verbatim, which is why a mapper refusal names the field
it refused.

This is the one place in the codebase that catches ``Exception`` and turns
it into a response rather than re-raising it as an ``InfrastructureError``
the way the outbox publisher and the notification sender do, and it is
allowed to because it sits on the edge of the process. Nothing above a
handler could turn an unexpected exception into a response, and an exception
that escapes here reaches aiohttp's own handler, which answers with an HTML
``500`` the 1C module cannot read a code out of.
Every such catch logs the traceback first: the response is for the sender,
the log is for whoever operates the receiver, and swallowing the one to
produce the other is the mistake the rule against blind catches exists for.

``web.HTTPException`` is let through untouched. aiohttp raises it for the
things it decides itself — a body over ``client_max_size``, a path nothing
is routed at — and it already is the response it means to send.
"""

import logging
from http import HTTPStatus
from typing import Final

from aiohttp import web
from aiohttp.typedefs import Handler

from goldy.application.error import CatalogSnapshotError
from goldy.domain.common.error import AppError
from goldy.infrastructure.errors import CatalogSourceReadError

logger: Final[logging.Logger] = logging.getLogger(__name__)


def error_response(status: HTTPStatus, error: str, detail: str) -> web.Response:
    """The failure body the 1C module parses, with the code it branches on."""
    return web.json_response({"error": error, "detail": detail}, status=status)


@web.middleware
async def translate_errors(
    request: web.Request,
    handler: Handler,
) -> web.StreamResponse:
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except CatalogSourceReadError as exc:
        logger.warning(
            "catalog_receiver: %s %s from %s rejected: %s",
            request.method,
            request.path,
            request.remote,
            exc,
        )
        return error_response(HTTPStatus.BAD_REQUEST, "bad_request", str(exc))
    except CatalogSnapshotError as exc:
        logger.warning(
            "catalog_receiver: %s %s from %s left the projection unusable: %s",
            request.method,
            request.path,
            request.remote,
            exc,
        )
        return error_response(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "snapshot_rejected",
            str(exc),
        )
    except AppError as exc:
        logger.exception(
            "catalog_receiver: %s %s from %s failed",
            request.method,
            request.path,
            request.remote,
        )
        return error_response(HTTPStatus.INTERNAL_SERVER_ERROR, "internal", str(exc))
    except Exception as exc:
        logger.exception(
            "catalog_receiver: %s %s from %s failed unexpectedly",
            request.method,
            request.path,
            request.remote,
        )
        return error_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "internal",
            f"{type(exc).__name__}; see the receiver log.",
        )
