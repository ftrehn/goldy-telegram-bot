"""What the receiver makes of the requests 1C sends it, over a real socket.

The decisions under test are the receiver's own: that nothing answers without
the token and that every refusal of it looks the same; that a batch body
becomes ``ImportCatalogCommand`` and a finalisation body becomes
``FinalizeCatalogImportCommand`` with the scope read by the same rules; and
that each kind of failure below the handler comes back as the status code
and the ``error`` code the 1C module branches on, with a ``detail`` that
names the field when there is one to name.
"""

import json
from http import HTTPStatus
from pathlib import Path
from typing import Final

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.ports.catalog import CatalogScope, CatalogScopeKind
from goldy.application.error import CatalogSnapshotError
from tests.unit.factories.catalog_factories import (
    make_batch_document,
    make_batch_product,
)
from tests.unit.infrastructure.catalog_receiver.conftest import (
    MAX_BODY_BYTES,
    TOKEN,
    ReceiverClient,
)
from tests.unit.stubs.catalog import RecordingCatalogSender

EXAMPLE_SNAPSHOT: Final[Path] = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "design"
    / "catalog-snapshot.example.json"
)
"""The documented example of the contract, which is also what 1C is built against."""

AUTHORIZED: Final[dict[str, str]] = {"Authorization": f"Bearer {TOKEN}"}


async def test_a_request_without_a_token_is_refused_before_anything_else(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    response = await client.post("/catalog/batches", json=make_batch_document())

    assert response.status == HTTPStatus.UNAUTHORIZED
    assert await response.json() == {"error": "unauthorized"}
    assert sender.requests == []


async def test_a_wrong_token_is_refused_with_the_same_answer_as_none(
    client: ReceiverClient,
) -> None:
    """Which of the two it was is not told, so nobody can be taught the difference."""
    wrong = await client.get(
        "/catalog/ping",
        headers={"Authorization": "Bearer not-the-token-0123456789abcdef"},
    )
    other_scheme = await client.get(
        "/catalog/ping",
        headers={"Authorization": f"Basic {TOKEN}"},
    )

    assert wrong.status == HTTPStatus.UNAUTHORIZED
    assert other_scheme.status == HTTPStatus.UNAUTHORIZED
    assert await wrong.json() == await other_scheme.json() == {"error": "unauthorized"}


async def test_ping_answers_that_the_token_and_the_address_are_right(
    client: ReceiverClient,
) -> None:
    response = await client.get("/catalog/ping", headers=AUTHORIZED)

    assert response.status == HTTPStatus.OK
    assert await response.json() == {"status": "ok"}


async def test_a_token_padded_in_the_environment_still_matches_the_one_1c_sends(
    padded_token_client: ReceiverClient,
) -> None:
    """Both sides trim: 1C its constant, the receiver what it keeps and what it reads.

    Kept raw, a token with a space on either side would pass the loader and
    then earn every batch a ``401``, with nothing in either log to say why.
    """
    response = await padded_token_client.get("/catalog/ping", headers=AUTHORIZED)

    assert response.status == HTTPStatus.OK


async def test_the_documented_example_becomes_an_import_of_its_batch(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    """The file the contract is documented by is accepted exactly as documented."""
    document = json.loads(EXAMPLE_SNAPSHOT.read_text(encoding="utf-8"))

    response = await client.post("/catalog/batches", json=document, headers=AUTHORIZED)

    assert response.status == HTTPStatus.OK
    [command] = sender.requests
    assert isinstance(command, ImportCatalogCommand)
    assert command.snapshot.batch_id == document["batch_id"]
    assert len(command.snapshot.products) == len(document["products"])


async def test_the_import_response_is_the_command_response_as_json(
    client: ReceiverClient,
) -> None:
    """1C reads ``accepted`` and ``discarded`` by the names the application gave them."""
    response = await client.post(
        "/catalog/batches",
        json=make_batch_document(),
        headers=AUTHORIZED,
    )

    assert await response.json() == {
        "batch_id": "ut-20260913-120000-abcd1234",
        "scope": "products",
        "accepted": 1,
        "discarded": 0,
    }


async def test_a_body_that_is_not_json_is_a_bad_request(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    response = await client.post(
        "/catalog/batches",
        data=b"{ this is not json",
        headers={**AUTHORIZED, "Content-Type": "application/json"},
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    body = await response.json()
    assert body["error"] == "bad_request"
    assert "not valid JSON" in body["detail"]
    assert sender.requests == []


async def test_a_body_in_an_encoding_that_does_not_exist_is_a_bad_request(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    """A charset nobody has heard of is the client's mistake, not a reason to retry.

    ``codecs`` raises ``LookupError`` for it rather than ``ValueError``, and
    left uncaught that reached 1C as an ``internal`` error with a traceback in
    the receiver log — "try again later" for a body that will never decode.
    """
    response = await client.post(
        "/catalog/batches",
        data=json.dumps(make_batch_document()).encode(),
        headers={**AUTHORIZED, "Content-Type": "application/json; charset=nope"},
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    body = await response.json()
    assert body["error"] == "bad_request"
    assert "nope" in body["detail"]
    assert sender.requests == []


async def test_a_body_missing_a_field_names_the_field_in_the_detail(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    """The detail lands in the 1C event log, where naming the field is the fix."""
    product = {"id": "3b7d5e60-0000-4000-8000-00000000000a", "name": "Болт"}

    response = await client.post(
        "/catalog/batches",
        json=make_batch_document(products=[product]),
        headers=AUTHORIZED,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    body = await response.json()
    assert body["error"] == "bad_request"
    assert "products[0]" in body["detail"]
    assert "sku" in body["detail"]
    assert sender.requests == []


async def test_a_finalisation_becomes_the_command_with_its_scope_read_whole(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    sender.swept = 7

    response = await client.post(
        "/catalog/batches/ut-20260913-120000-abcd1234/finalize",
        json={"scope": {"kind": "prices", "price_type_id": "pt-wholesale"}},
        headers=AUTHORIZED,
    )

    assert response.status == HTTPStatus.OK
    [command] = sender.requests
    assert isinstance(command, FinalizeCatalogImportCommand)
    assert command.batch_id == "ut-20260913-120000-abcd1234"
    assert command.scope == CatalogScope(
        kind=CatalogScopeKind.PRICES,
        price_type_id="pt-wholesale",
    )
    assert await response.json() == {
        "batch_id": "ut-20260913-120000-abcd1234",
        "scope": "prices:pt-wholesale",
        "swept": 7,
    }


async def test_a_finalisation_with_a_blank_batch_id_in_the_path_is_a_bad_request(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    """A whitespace segment matches the route, and a blank id would sweep everything.

    The sweep selects ``batch_id != <id>``, so an id of ``' '`` names every
    row in the scope as stale. The mapper refuses a blank ``batch_id`` in a
    body; the path has to be refused by the same rule.
    """
    response = await client.post(
        "/catalog/batches/%20/finalize",
        json={"scope": {"kind": "products"}},
        headers=AUTHORIZED,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    body = await response.json()
    assert body["error"] == "bad_request"
    assert "batch id" in body["detail"]
    assert sender.requests == []


async def test_a_finalisation_without_a_scope_is_a_bad_request(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    response = await client.post(
        "/catalog/batches/ut-20260913-120000-abcd1234/finalize",
        json={"kind": "prices"},
        headers=AUTHORIZED,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    body = await response.json()
    assert body["error"] == "bad_request"
    assert "'scope'" in body["detail"]
    assert sender.requests == []


async def test_a_finalisation_with_a_wrong_scope_names_the_field_under_its_key(
    client: ReceiverClient,
) -> None:
    """A typo in the kind would otherwise sweep the wrong part of the catalog."""
    response = await client.post(
        "/catalog/batches/ut-20260913-120000-abcd1234/finalize",
        json={"scope": {"kind": "pricez"}},
        headers=AUTHORIZED,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    body = await response.json()
    assert "scope.kind" in body["detail"]
    assert "pricez" in body["detail"]


async def test_a_snapshot_the_handler_refuses_is_reported_as_rejected(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    """The batches were fine; the projection they left is not. 1C must tell them apart."""
    sender.failure = CatalogSnapshotError("Default price type 'pt-retail' is gone.")

    response = await client.post(
        "/catalog/batches/ut-20260913-120000-abcd1234/finalize",
        json={"scope": {"kind": "price_types"}},
        headers=AUTHORIZED,
    )

    assert response.status == HTTPStatus.UNPROCESSABLE_CONTENT
    assert await response.json() == {
        "error": "snapshot_rejected",
        "detail": "Default price type 'pt-retail' is gone.",
    }


async def test_an_unexpected_failure_is_an_internal_error_that_names_no_internals(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    """Still JSON, so the 1C module can read a code out of it and retry later."""
    sender.failure = RuntimeError("connection to server at 10.0.0.5 refused")

    response = await client.post(
        "/catalog/batches",
        json=make_batch_document(),
        headers=AUTHORIZED,
    )

    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
    body = await response.json()
    assert body["error"] == "internal"
    assert "RuntimeError" in body["detail"]
    assert "10.0.0.5" not in body["detail"]


async def test_a_body_over_the_limit_is_refused_by_aiohttp_itself(
    client: ReceiverClient,
    sender: RecordingCatalogSender,
) -> None:
    oversized = make_batch_document(
        products=[make_batch_product()] * (MAX_BODY_BYTES // 50),
    )
    assert len(json.dumps(oversized).encode()) > MAX_BODY_BYTES

    response = await client.post("/catalog/batches", json=oversized, headers=AUTHORIZED)

    assert response.status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert sender.requests == []
