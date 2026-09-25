"""The site as seen from one linked person: linking, their prices, their money.

Each adapter is small, and what is worth pinning down is the shape of what it
sends, how it reads what the site sends back and — the part every adapter in
this module promises — which of the site's codes become which typed error.
"""

import json
from decimal import Decimal

import httpx
import pytest

from goldy.application.common.ports.site import (
    SiteCustomer,
    SiteLinkRequest,
    SitePriceRequest,
)
from goldy.application.common.views.site import SiteLinkPreviewView
from goldy.application.error import (
    SiteFinanceDeniedError,
    SiteLinkCodeInvalidError,
    SiteLinkForbiddenError,
    SiteSubjectTakenError,
    SiteUnavailableError,
)
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.quantity import Quantity
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.infrastructure.adapters.site_api.site_customer_adapters import (
    MAX_PRICED_ITEMS,
    HttpSiteFinance,
    HttpSiteLinking,
    HttpSitePricing,
)
from tests.unit.factories.site_api_factories import make_site_api_client
from tests.unit.stubs.site_api import ScriptedTransport, envelope

# --- HttpSiteLinking -------------------------------------------------------


async def test_preview_sends_the_code_and_the_platform() -> None:
    transport = ScriptedTransport(
        envelope(
            {
                "customer": {
                    "name": "Иван И.",
                    "email": "i***@example.ru",
                    "company": "ТД «Ромашка»",
                },
            },
        ),
    )

    result = await HttpSiteLinking(make_site_api_client(transport)).preview(
        "CODE123",
        MessengerPlatform.TELEGRAM,
    )

    assert result == SiteLinkPreviewView(
        customer_name="Иван И.",
        email="i***@example.ru",
        company_name="ТД «Ромашка»",
    )
    request = transport.requests[0]
    assert request.method == "POST"
    assert json.loads(request.content) == {"code": "CODE123", "platform": "telegram"}


async def test_preview_reraises_an_invalid_code() -> None:
    transport = ScriptedTransport(
        httpx.Response(422, json={"error": {"code": "link_code_invalid"}}),
    )

    with pytest.raises(SiteLinkCodeInvalidError):
        await HttpSiteLinking(make_site_api_client(transport)).preview(
            "STALE",
            MessengerPlatform.TELEGRAM,
        )


@pytest.mark.parametrize("code", ("staff_link_forbidden", "customer_blocked"))
async def test_preview_reraises_the_sites_refusal_to_link_at_all(code: str) -> None:
    transport = ScriptedTransport(httpx.Response(422, json={"error": {"code": code}}))

    with pytest.raises(SiteLinkForbiddenError):
        await HttpSiteLinking(make_site_api_client(transport)).preview(
            "CODE123",
            MessengerPlatform.TELEGRAM,
        )


async def test_confirm_sends_the_optional_fields_only_when_given() -> None:
    transport = ScriptedTransport(
        envelope({"customer": {"name": "Иван Иванов", "audience": "retail"}}),
    )
    request = SiteLinkRequest(
        code="CODE123",
        subject="11111111-1111-1111-1111-111111111111",
        platform=MessengerPlatform.MAX,
        label=None,
        phone=None,
    )

    await HttpSiteLinking(make_site_api_client(transport)).confirm(request)

    assert json.loads(transport.requests[0].content) == {
        "code": "CODE123",
        "subject": "11111111-1111-1111-1111-111111111111",
        "platform": "max",
    }


async def test_confirm_reads_the_linked_customer_including_a_nested_company() -> None:
    transport = ScriptedTransport(
        envelope(
            {
                "customer": {
                    "name": "Иван Иванов",
                    "company": {"name": "ТД «Ромашка»"},
                    "audience": "wholesale",
                    "finance_access": True,
                },
            },
        ),
    )
    request = SiteLinkRequest(
        code="CODE123",
        subject="user-1",
        platform=MessengerPlatform.TELEGRAM,
        label="Telegram",
        phone="+79991234567",
    )

    customer = await HttpSiteLinking(make_site_api_client(transport)).confirm(request)

    assert customer == SiteCustomer(
        name="Иван Иванов",
        company_name="ТД «Ромашка»",
        is_wholesale=True,
        finance_access=True,
    )
    assert json.loads(transport.requests[0].content) == {
        "code": "CODE123",
        "subject": "user-1",
        "platform": "telegram",
        "label": "Telegram",
        "phone": "+79991234567",
    }


async def test_confirm_reraises_a_subject_already_linked_elsewhere() -> None:
    transport = ScriptedTransport(
        httpx.Response(422, json={"error": {"code": "subject_taken"}})
    )
    request = SiteLinkRequest(
        code="CODE123",
        subject="user-1",
        platform=MessengerPlatform.TELEGRAM,
        label=None,
        phone=None,
    )

    with pytest.raises(SiteSubjectTakenError):
        await HttpSiteLinking(make_site_api_client(transport)).confirm(request)


async def test_revoke_deletes_the_link_by_the_quoted_subject() -> None:
    transport = ScriptedTransport(httpx.Response(204))

    await HttpSiteLinking(make_site_api_client(transport)).revoke("user/needs quoting")

    request = transport.requests[0]
    assert request.method == "DELETE"
    assert str(request.url) == "https://tkgoldy.ru/api/v1/links/user%2Fneeds%20quoting"


async def test_revoke_reports_an_outage_rather_than_a_bare_transport_error() -> None:
    transport = ScriptedTransport(httpx.Response(503))

    with pytest.raises(SiteUnavailableError):
        await HttpSiteLinking(make_site_api_client(transport)).revoke("user-1")


# --- HttpSitePricing --------------------------------------------------------


def _priced_items(count: int) -> list[SitePriceRequest]:
    return [
        SitePriceRequest(product_id=ProductId(value=f"p{i}"), quantity=Quantity(value=1))
        for i in range(count)
    ]


async def test_prices_for_splits_more_than_two_hundred_items_into_chunks() -> None:
    items = _priced_items(MAX_PRICED_ITEMS + 1)
    first_chunk, second_chunk = items[:MAX_PRICED_ITEMS], items[MAX_PRICED_ITEMS:]
    transport = ScriptedTransport(
        envelope(
            [
                {
                    "id": item.product_id.value,
                    "available": True,
                    "price": {"amount": "10.00", "currency": "RUB"},
                }
                for item in first_chunk
            ],
        ),
        envelope(
            [
                {
                    "id": item.product_id.value,
                    "available": True,
                    "price": {"amount": "10.00", "currency": "RUB"},
                }
                for item in second_chunk
            ],
        ),
    )

    prices = await HttpSitePricing(make_site_api_client(transport)).prices_for(
        "user-1",
        items,
    )

    assert len(transport.requests) == 2
    assert len(json.loads(transport.requests[0].content)["items"]) == MAX_PRICED_ITEMS
    assert len(json.loads(transport.requests[1].content)["items"]) == 1
    assert len(prices) == MAX_PRICED_ITEMS + 1
    assert transport.requests[0].headers["X-Customer"] == "user-1"


async def test_prices_for_reads_an_unavailable_position_with_its_reason() -> None:
    transport = ScriptedTransport(
        envelope([{"id": "p1", "available": False, "reason": "hidden"}]),
    )

    prices = await HttpSitePricing(make_site_api_client(transport)).prices_for(
        "user-1",
        _priced_items(1),
    )

    assert prices[0].unit_price is None
    assert prices[0].reason == "hidden"


async def test_prices_for_defaults_the_reason_when_the_site_gives_none() -> None:
    transport = ScriptedTransport(envelope([{"id": "p1", "available": False}]))

    prices = await HttpSitePricing(make_site_api_client(transport)).prices_for(
        "user-1",
        _priced_items(1),
    )

    assert prices[0].reason == "unavailable"


async def test_prices_for_reads_a_priced_position() -> None:
    transport = ScriptedTransport(
        envelope([
            {
                "id": "p1",
                "available": True,
                "price": {"amount": "412.50", "currency": "RUB"},
            }
        ]),
    )

    prices = await HttpSitePricing(make_site_api_client(transport)).prices_for(
        "user-1",
        _priced_items(1),
    )

    assert prices[0].unit_price is not None
    assert prices[0].unit_price.amount == Decimal("412.50")
    assert prices[0].reason is None


# --- HttpSiteFinance ---------------------------------------------------------


async def test_finance_denied_carries_the_sites_own_reason() -> None:
    transport = ScriptedTransport(
        httpx.Response(
            403,
            json={
                "error": {"code": "finance_denied", "details": {"reason": "not_approved"}}
            },
        ),
    )

    with pytest.raises(SiteFinanceDeniedError) as failure:
        await HttpSiteFinance(make_site_api_client(transport)).summary("user-1")

    assert failure.value.reason == "not_approved"


async def test_finance_with_no_bridge_to_1c_is_reported_as_not_configured() -> None:
    transport = ScriptedTransport(
        httpx.Response(422, json={"error": {"code": "erp_not_configured"}}),
    )

    with pytest.raises(SiteFinanceDeniedError) as failure:
        await HttpSiteFinance(make_site_api_client(transport)).summary("user-1")

    assert failure.value.reason == "not_configured"


async def test_finance_summary_reads_debt_and_the_erp_freshness() -> None:
    transport = ScriptedTransport(
        envelope(
            {
                "company": {"name": "ТД «Ромашка»"},
                "debt": {
                    "total": {"debt": "1000.00", "advance": "0.00", "currency": "RUB"}
                },
                "overdue": {"total_overdue": "200.00", "max_days_overdue": 5},
                "credit_limit": {"amount": "5000.00", "available": "3000.00"},
            },
            erp={
                "source": "1c",
                "as_of": "2026-09-25T12:00:00+03:00",
                "stale": False,
                "partial": False,
            },
        ),
    )

    summary = await HttpSiteFinance(make_site_api_client(transport)).summary("user-1")

    assert summary.company_name == "ТД «Ромашка»"
    assert summary.erp_linked is True
    assert summary.debt is not None
    assert summary.debt.amount == Decimal("1000.00")
    assert summary.overdue is not None
    assert summary.overdue.amount == Decimal("200.00")
    assert summary.max_days_overdue == 5
    assert summary.credit_limit is not None
    assert summary.credit_limit.amount == Decimal("5000.00")
    assert summary.is_stale is False
    assert summary.is_partial is False


async def test_finance_with_no_erp_link_at_all_says_so() -> None:
    transport = ScriptedTransport(
        envelope(
            {"company": None, "debt": None, "overdue": None, "credit_limit": None},
            erp={"source": "none"},
        ),
    )

    summary = await HttpSiteFinance(make_site_api_client(transport)).summary("user-1")

    assert summary.erp_linked is False
    assert summary.debt is None
