"""The three routes 1C calls, each a thin turn of a body into a command.

Ordinary aiohttp handlers reaching the container through ``FromDishka``, the
way the RabbitMQ subscribers reach it: the request scope is opened per
request by the middleware ``setup_dishka`` installs, and ``@inject`` fills
the dependencies out of it. There is no class holding a container and
nothing here knows how a session or a transaction is made.

A handler does exactly three things — decode the body, hand it to the
mapper, send the command — and nothing about what the command does. Whether
a batch is upserted, what a sweep removes and why a finalisation over price
types can be refused are the handlers' business in ``application/commands``;
this module is where the HTTP envelope is taken off, and where it is put back
on: the response body is the command's own response, serialised as it is,
because both response dataclasses are flat records of primitives and 1C
reads them by the names the application gave the fields.

The mapper reads the whole batch body, but of a finalisation body only the
value under ``scope``. Finding the key is done here, because the mapper is
handed a scope wherever one came from and only the handler knows it came
wrapped; a body without the key is refused with the same error, and the same
``400``, as a body with a wrong field in it.
"""

import dataclasses
import logging
from typing import Final

from aiohttp import web
from dishka.integrations.aiohttp import FromDishka, inject

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.infrastructure.adapters.catalog.catalog_snapshot_mapper import (
    CatalogSnapshotMapper,
)
from goldy.infrastructure.errors import CatalogSourceReadError

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def ping(_request: web.Request) -> web.Response:
    """Answers that the receiver is up and the token was accepted.

    The token check is the whole of what this route is for — a ``200`` here
    tells the 1C administrator the address and the secret are right before the
    first batch is built. Nothing is resolved out of the request scope, so
    this is not a check of the database, deliberately: a receiver whose
    database is down should say so with a ``500`` on the first batch rather
    than be indistinguishable from one that is not listening.

    Async with nothing to await because aiohttp refuses a plain function as a
    handler at route registration — the same contract the dialog getters are
    exempted from ``RUF029`` for in ``ruff.toml``.
    """
    return web.json_response({"status": "ok"})


@inject
async def receive_batch(
    request: web.Request,
    sender: FromDishka[Sender],
    mapper: FromDishka[CatalogSnapshotMapper],
) -> web.Response:
    snapshot = mapper.to_snapshot(await _read_json(request))

    response = await sender.send(ImportCatalogCommand(snapshot=snapshot))

    logger.info(
        "catalog_receiver: batch=%s scope=%s accepted=%d discarded=%d client=%s",
        response.batch_id,
        response.scope,
        response.accepted,
        response.discarded,
        request.remote,
    )

    return web.json_response(dataclasses.asdict(response))


@inject
async def finalize_batch(
    request: web.Request,
    sender: FromDishka[Sender],
    mapper: FromDishka[CatalogSnapshotMapper],
) -> web.Response:
    batch_id = _batch_id_of(request)
    scope = mapper.to_scope(_scope_of(await _read_json(request)))

    response = await sender.send(
        FinalizeCatalogImportCommand(batch_id=batch_id, scope=scope),
    )

    logger.info(
        "catalog_receiver: batch=%s scope=%s swept=%d client=%s",
        response.batch_id,
        response.scope,
        response.swept,
        request.remote,
    )

    return web.json_response(dataclasses.asdict(response))


ROUTES: Final[tuple[web.RouteDef, ...]] = (
    web.get("/catalog/ping", ping),
    web.post("/catalog/batches", receive_batch),
    web.post("/catalog/batches/{batch_id}/finalize", finalize_batch),
)
"""The receiver's whole surface, in the order the 1C module calls it."""


def _batch_id_of(request: web.Request) -> str:
    """The batch id in the path of a finalisation, refused when it is blank.

    The router already answers an empty segment with a ``404``, but a segment
    of whitespace matches the route, and the mapper's rule that ``batch_id``
    in a batch body must not be blank does not reach a path. Let through, a
    blank id would make the sweep ``batch_id != ' '`` — every row in the
    scope — so it is refused here with the same ``400`` as a blank one in a
    body, before the body is even read.

    Raises:
        CatalogSourceReadError: the path segment is empty once stripped.
    """
    batch_id: str = request.match_info["batch_id"]

    if not batch_id.strip():
        msg = "The batch id in the path must not be blank."
        raise CatalogSourceReadError(msg)

    return batch_id


async def _read_json(request: web.Request) -> object:
    """Whatever JSON the body spells.

    A body over ``client_max_size`` is refused inside ``request.json()`` with
    aiohttp's own ``413``, which passes through here untouched — it is not
    a ``ValueError`` and must not be reported as one.

    ``LookupError`` is caught beside ``ValueError`` because that is what
    ``codecs`` raises for a charset that does not exist: a client declaring
    ``charset=nope`` has sent a bad request, not broken the receiver, and
    must not be told to try again later.

    Raises:
        CatalogSourceReadError: the body is not JSON at all, not text in the
            encoding the request declared, or declares an encoding there is
            no codec for.
    """
    try:
        document: object = await request.json()
    except (ValueError, LookupError) as exc:
        msg = f"The request body is not valid JSON: {exc}."
        raise CatalogSourceReadError(msg) from exc

    return document


def _scope_of(document: object) -> object:
    """The value under ``scope`` of a finalisation body.

    Raises:
        CatalogSourceReadError: the body is not an object, or has no such key.
    """
    if not isinstance(document, dict) or "scope" not in document:
        msg = "The finalisation body must be a JSON object with a 'scope' key."
        raise CatalogSourceReadError(msg)

    scope: object = document["scope"]
    return scope
