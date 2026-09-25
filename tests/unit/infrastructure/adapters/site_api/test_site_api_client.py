"""How the site API client reads the site's answers — and its failures.

Everything the rest of the bot knows about the site's transport is decided
here: the headers every request carries, the envelope, the cursor, and which
failures are worth retrying. The last one is what the tests are mostly about,
together with the promise every adapter makes — no httpx exception leaves it.
"""

import httpx
import pytest

from goldy.infrastructure.adapters.site_api.site_api_client import REQUEST_ID_HEADER
from goldy.infrastructure.errors import (
    InfrastructureError,
    SiteApiError,
    SiteApiRejectedError,
    SiteApiResponseError,
    SiteApiUnavailableError,
)
from tests.unit.factories.site_api_factories import SITE_API_TOKEN, make_site_api_client
from tests.unit.stubs.site_api import ScriptedTransport, envelope


async def test_every_request_carries_the_token_and_a_request_id() -> None:
    transport = ScriptedTransport(envelope([]))

    await make_site_api_client(transport).get("catalog/sections")

    request = transport.requests[0]
    assert request.headers["Authorization"] == f"Bearer {SITE_API_TOKEN}"
    assert request.headers["Accept"] == "application/json"
    assert len(request.headers[REQUEST_ID_HEADER]) == 32


async def test_a_path_is_appended_to_the_api_root() -> None:
    transport = ScriptedTransport(envelope([]))

    await make_site_api_client(transport).get("catalog/sections")

    assert str(transport.requests[0].url) == "https://tkgoldy.ru/api/v1/catalog/sections"


async def test_the_envelope_is_unwrapped_and_the_site_request_id_kept() -> None:
    answer = httpx.Response(
        200,
        json={"data": [{"id": "BASE"}], "meta": {"total": 1}},
        headers={REQUEST_ID_HEADER: "site-echo"},
    )

    response = await make_site_api_client(ScriptedTransport(answer)).get("x")

    assert response.data == [{"id": "BASE"}]
    assert response.meta == {"total": 1}
    assert response.request_id == "site-echo"


async def test_pages_are_followed_by_cursor_until_it_runs_out() -> None:
    transport = ScriptedTransport(
        envelope([1, 2], next_cursor="c2"),
        envelope([3], next_cursor="c3"),
        envelope([], next_cursor=None),
    )

    pages = [
        page.data
        async for page in make_site_api_client(transport).paginate("items", limit=2)
    ]

    assert pages == [[1, 2], [3], []]
    params = [dict(request.url.params) for request in transport.requests]
    assert params == [
        {"limit": "2"},
        {"limit": "2", "cursor": "c2"},
        {"limit": "2", "cursor": "c3"},
    ]


async def test_a_cursor_handed_back_twice_is_refused_rather_than_followed() -> None:
    """Following it would import the same page forever."""
    transport = ScriptedTransport(
        envelope([1], next_cursor="same"),
        envelope([2], next_cursor="same"),
    )
    client = make_site_api_client(transport)

    with pytest.raises(SiteApiResponseError):
        _ = [page async for page in client.paginate("items", limit=1)]


@pytest.mark.parametrize("status", (401, 403, 404, 422))
async def test_a_refusal_is_not_worth_retrying_and_keeps_the_site_code(
    status: int,
) -> None:
    answer = httpx.Response(
        status,
        json={"error": {"code": "unauthorized", "message": "…"}, "meta": {}},
    )

    with pytest.raises(SiteApiRejectedError) as failure:
        await make_site_api_client(ScriptedTransport(answer)).get("x")

    assert failure.value.status == status
    assert failure.value.code == "unauthorized"


async def test_too_many_requests_is_worth_retrying_after_the_site_says() -> None:
    answer = httpx.Response(
        429,
        json={"error": {"code": "rate_limited"}},
        headers={"Retry-After": "17"},
    )

    with pytest.raises(SiteApiUnavailableError) as failure:
        await make_site_api_client(ScriptedTransport(answer)).get("x")

    assert failure.value.code == "rate_limited"
    assert failure.value.retry_after == pytest.approx(17.0)


@pytest.mark.parametrize("status", (500, 502, 503))
async def test_a_server_error_is_worth_retrying_even_with_an_html_body(
    status: int,
) -> None:
    """A 502 from the proxy in front of the site has no envelope to read a code from."""
    answer = httpx.Response(status, text="<html>Bad Gateway</html>")

    with pytest.raises(SiteApiUnavailableError) as failure:
        await make_site_api_client(ScriptedTransport(answer)).get("x")

    assert failure.value.status == status
    assert failure.value.code is None


@pytest.mark.parametrize(
    "error",
    (
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("slow"),
        httpx.RemoteProtocolError("cut"),
    ),
)
async def test_a_transport_failure_is_worth_retrying(error: Exception) -> None:
    with pytest.raises(SiteApiUnavailableError) as failure:
        await make_site_api_client(ScriptedTransport(error)).get("x")

    assert failure.value.status is None
    assert failure.value.request_id is not None


@pytest.mark.parametrize(
    "answer",
    (
        httpx.Response(200, text="not json"),
        httpx.Response(200, json=[1, 2, 3]),
        httpx.Response(200, json={"meta": {}}),
        httpx.Response(200, json={"data": [], "meta": "oops"}),
        httpx.Response(302, headers={"Location": "https://elsewhere.example/"}),
    ),
)
async def test_an_answer_that_is_not_the_contract_is_a_response_error(
    answer: httpx.Response,
) -> None:
    with pytest.raises(SiteApiResponseError):
        await make_site_api_client(ScriptedTransport(answer)).get("x")


async def test_no_content_is_an_empty_answer_rather_than_a_parsing_failure() -> None:
    response = await make_site_api_client(ScriptedTransport(httpx.Response(204))).get("x")

    assert response.data is None


def test_every_client_error_is_an_infrastructure_error() -> None:
    """Callers catch one family; nothing from httpx reaches them."""
    errors = (
        SiteApiUnavailableError("x"),
        SiteApiRejectedError("x"),
        SiteApiResponseError("x"),
    )

    assert all(isinstance(error, SiteApiError) for error in errors)
    assert all(isinstance(error, InfrastructureError) for error in errors)
