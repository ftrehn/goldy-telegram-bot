"""Handing orders to the site, cancelling them, and reading the feed back.

What is worth pinning down: the shape ``POST /orders`` and the cancel endpoint
take, which of the site's refusal codes become an order refusal versus a stale
link versus "not cancellable any more", and that the feed's ``updated_since``
travels on the first page of a pass only — repeating it on every page would
ask the site the same "since forever" question after the cursor already moved
it forward.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from goldy.application.common.ports.site import (
    SiteOrderItem,
    SiteOrderState,
    SiteOrderSubmission,
)
from goldy.application.error import (
    SiteCustomerNotLinkedError,
    SiteOrderNotCancellableError,
    SiteOrderRejectedError,
    SiteUnavailableError,
)
from goldy.domain.catalog.values.product_id import ProductId
from goldy.infrastructure.adapters.site_api.site_orders_adapter import HttpSiteOrders
from tests.unit.factories.site_api_factories import make_site_api_client
from tests.unit.stubs.site_api import ScriptedTransport, envelope


def _order_document(
    external_id: str = "ext-1",
    site_order_id: int = 555,
    state: str = "new",
) -> dict[str, object]:
    return {
        "external_id": external_id,
        "site_order_id": site_order_id,
        "number": "ГКУТ-000555",
        "status": {"code": "N", "name": "Принят", "state": state},
        "updated_at": "2026-09-25T12:00:00+03:00",
    }


def _submission(
    subject: str | None = None,
    comment: str | None = "Please call before delivery",
) -> SiteOrderSubmission:
    return SiteOrderSubmission(
        external_id="ext-1",
        number="240913-3K7QXA",
        subject=subject,
        items=[
            SiteOrderItem(
                product_id=ProductId(value="p1"),
                quantity=2,
                unit_price=Decimal("19.99"),
            ),
        ],
        expected_total=Decimal("39.98"),
        recipient_name="Иван Иванов",
        recipient_phone="+79991234567",
        address="Москва, Ленина 1",
        comment=comment,
    )


# --- submit ------------------------------------------------------------------


async def test_submit_sends_the_order_in_the_sites_shape() -> None:
    transport = ScriptedTransport(envelope(_order_document()))

    status = await HttpSiteOrders(make_site_api_client(transport)).submit(
        _submission(subject="user-1"),
    )

    request = transport.requests[0]
    assert json.loads(request.content) == {
        "external_id": "ext-1",
        "number": "240913-3K7QXA",
        "items": [{"id": "p1", "quantity": "2", "price": "19.99"}],
        "expected_total": "39.98",
        "recipient": {"name": "Иван Иванов", "phone": "+79991234567"},
        "delivery": {"address": "Москва, Ленина 1"},
        "comment": "Please call before delivery",
    }
    assert request.headers["X-Customer"] == "user-1"
    assert status.external_id == "ext-1"
    assert status.site_order_id == 555
    assert status.state is SiteOrderState.NEW


async def test_submit_as_a_guest_carries_no_customer_header() -> None:
    transport = ScriptedTransport(envelope(_order_document()))

    await HttpSiteOrders(make_site_api_client(transport)).submit(
        _submission(subject=None)
    )

    assert "X-Customer" not in transport.requests[0].headers


async def test_submit_refused_for_a_reason_of_the_orders_own_is_a_rejection() -> None:
    transport = ScriptedTransport(
        httpx.Response(422, json={"error": {"code": "prices_changed"}}),
    )

    with pytest.raises(SiteOrderRejectedError) as failure:
        await HttpSiteOrders(make_site_api_client(transport)).submit(_submission())

    assert failure.value.code == "prices_changed"


async def test_submit_when_the_site_no_longer_knows_the_subject() -> None:
    """Not the same failure as a refusal — the link went stale, not the order."""
    transport = ScriptedTransport(
        httpx.Response(409, json={"error": {"code": "customer_not_linked"}}),
    )

    with pytest.raises(SiteCustomerNotLinkedError):
        await HttpSiteOrders(make_site_api_client(transport)).submit(
            _submission(subject="user-1"),
        )


async def test_submit_when_the_site_does_not_answer() -> None:
    transport = ScriptedTransport(httpx.Response(503))

    with pytest.raises(SiteUnavailableError):
        await HttpSiteOrders(make_site_api_client(transport)).submit(_submission())


# --- cancel ------------------------------------------------------------------


async def test_cancel_sends_the_reason_only_when_given() -> None:
    transport = ScriptedTransport(envelope(_order_document(state="cancelled")))

    await HttpSiteOrders(make_site_api_client(transport)).cancel("ext-1", "user-1", None)

    request = transport.requests[0]
    assert request.url.path == "/api/v1/orders/ext-1/cancel"
    assert json.loads(request.content) == {}
    assert request.headers["X-Customer"] == "user-1"


async def test_cancel_quotes_the_external_id_in_the_path() -> None:
    transport = ScriptedTransport(envelope(_order_document(external_id="ord/1")))

    await HttpSiteOrders(make_site_api_client(transport)).cancel(
        "ord/1", None, "changed mind"
    )

    request = transport.requests[0]
    assert str(request.url) == "https://tkgoldy.ru/api/v1/orders/ord%2F1/cancel"
    assert json.loads(request.content) == {"reason": "changed mind"}


async def test_cancel_refused_because_the_shop_already_took_it_into_work() -> None:
    transport = ScriptedTransport(
        httpx.Response(409, json={"error": {"code": "order_not_cancellable"}}),
    )

    with pytest.raises(SiteOrderNotCancellableError):
        await HttpSiteOrders(make_site_api_client(transport)).cancel("ext-1", None, None)


async def test_cancel_refused_for_a_reason_of_the_orders_own_is_still_a_rejection() -> (
    None
):
    transport = ScriptedTransport(
        httpx.Response(404, json={"error": {"code": "order_not_found"}}),
    )

    with pytest.raises(SiteOrderRejectedError) as failure:
        await HttpSiteOrders(make_site_api_client(transport)).cancel("ext-1", None, None)

    assert failure.value.code == "order_not_found"


# --- changes -------------------------------------------------------------------


async def test_the_feed_asks_updated_since_only_on_the_first_page() -> None:
    transport = ScriptedTransport(
        envelope([_order_document("ext-1")], next_cursor="c2"),
        envelope([_order_document("ext-2")], next_cursor=None),
    )
    since = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)

    pages = [
        page
        async for page in HttpSiteOrders(make_site_api_client(transport)).changes(since)
    ]

    assert [status.external_id for page in pages for status in page] == ["ext-1", "ext-2"]
    first_params = dict(transport.requests[0].url.params)
    second_params = dict(transport.requests[1].url.params)
    assert first_params["updated_since"] == since.isoformat()
    assert "updated_since" not in second_params
    assert second_params["cursor"] == "c2"


async def test_the_feed_reports_an_outage_rather_than_a_bare_transport_error() -> None:
    transport = ScriptedTransport(httpx.ConnectError("refused"))

    with pytest.raises(SiteUnavailableError):
        async for _page in HttpSiteOrders(make_site_api_client(transport)).changes(
            datetime(2026, 9, 25, 10, 0, tzinfo=UTC),
        ):
            pass
