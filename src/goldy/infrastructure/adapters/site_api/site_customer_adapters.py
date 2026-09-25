"""The site as seen from one linked person: linking, their prices, their money.

Three ports, three small classes over one :class:`SiteApiClient`. Each knows
its endpoints' codes and turns them into the errors its port promises; what
every endpoint shares is handled once, in ``reraise_common``.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final, NoReturn, override
from urllib.parse import quote

from goldy.application.common.ports.site import (
    SiteCustomer,
    SiteFinance,
    SiteLinkRequest,
    SiteLinking,
    SitePrice,
    SitePriceRequest,
    SitePricing,
)
from goldy.application.common.views.money import MoneyView
from goldy.application.common.views.site import (
    SiteFinanceSummaryView,
    SiteLinkPreviewView,
)
from goldy.application.error import (
    SiteFinanceDeniedError,
    SiteLinkCodeInvalidError,
    SiteLinkForbiddenError,
    SiteSubjectTakenError,
)
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.infrastructure.adapters.site_api.site_api_client import SiteApiClient
from goldy.infrastructure.adapters.site_api.site_documents import (
    as_list,
    as_object,
    decimal,
    flag,
    moment,
    money,
    optional_integer,
    optional_text,
    reraise_common,
    text,
)
from goldy.infrastructure.errors import SiteApiError, SiteApiRejectedError

MAX_PRICED_ITEMS: Final[int] = 200
"""The site prices at most this many positions per ``POST /me/prices``."""

_PLATFORMS: Final[dict[MessengerPlatform, str]] = {
    MessengerPlatform.TELEGRAM: "telegram",
    MessengerPlatform.MAX: "max",
}


def _platform(platform: MessengerPlatform) -> str:
    """The site's name for a platform — stated here, not borrowed from our enum."""
    return _PLATFORMS[platform]


def _customer(document: object) -> SiteCustomer:
    """``GET /me`` — and the ``customer`` inside ``POST /links`` — as ours."""
    customer = as_object(document, "a customer")
    company = customer.get("company")
    company_name = (
        None
        if company is None
        else optional_text(
            as_object(company, "a company"),
            "name",
        )
    )
    return SiteCustomer(
        name=text(customer, "name"),
        company_name=company_name,
        is_wholesale=customer.get("audience") == "wholesale",
        finance_access=flag(customer, "finance_access"),
    )


class HttpSiteLinking(SiteLinking):
    """``POST /links/preview``, ``POST /links`` and ``DELETE /links/{subject}``."""

    def __init__(self, client: SiteApiClient) -> None:
        self._client: Final[SiteApiClient] = client

    @override
    async def preview(
        self, code: str, platform: MessengerPlatform
    ) -> SiteLinkPreviewView:
        try:
            response = await self._client.post(
                "links/preview",
                {"code": code, "platform": _platform(platform)},
            )
        except SiteApiError as e:
            self._reraise(e, "links/preview")

        customer = as_object(
            as_object(response.data, "a preview").get("customer"), "a customer"
        )
        return SiteLinkPreviewView(
            customer_name=text(customer, "name"),
            email=optional_text(customer, "email"),
            company_name=optional_text(customer, "company"),
        )

    @override
    async def confirm(self, request: SiteLinkRequest) -> SiteCustomer:
        body: dict[str, object] = {
            "code": request.code,
            "subject": request.subject,
            "platform": _platform(request.platform),
        }
        if request.label is not None:
            body["label"] = request.label
        if request.phone is not None:
            body["phone"] = request.phone

        try:
            response = await self._client.post("links", body)
        except SiteApiError as e:
            self._reraise(e, "links")

        return _customer(as_object(response.data, "a link").get("customer"))

    @override
    async def revoke(self, subject: str) -> None:
        try:
            await self._client.delete(f"links/{quote(subject, safe='')}")
        except SiteApiError as e:
            reraise_common(e, "DELETE links/<subject>")

    @staticmethod
    def _reraise(error: SiteApiError, where: str) -> NoReturn:
        """The linking codes first, then what every endpoint shares.

        Raises:
            SiteLinkCodeInvalidError: ``link_code_invalid``.
            SiteLinkForbiddenError: ``staff_link_forbidden``, ``customer_blocked``.
            SiteSubjectTakenError: ``subject_taken``.
            SiteUnavailableError: the site did not answer.
            SiteApiError: anything else.
        """
        if isinstance(error, SiteApiRejectedError):
            if error.code == "link_code_invalid":
                msg = "The site does not know this linking code, or it expired."
                raise SiteLinkCodeInvalidError(msg) from error
            if error.code in {"staff_link_forbidden", "customer_blocked"}:
                msg = f"The site refuses to link this customer ({error.code})."
                raise SiteLinkForbiddenError(msg) from error
            if error.code == "subject_taken":
                msg = "The site has this person linked to another customer."
                raise SiteSubjectTakenError(msg) from error

        reraise_common(error, where)


class HttpSitePricing(SitePricing):
    """``POST /me/prices`` in chunks the site accepts."""

    def __init__(self, client: SiteApiClient) -> None:
        self._client: Final[SiteApiClient] = client

    @override
    async def prices_for(
        self,
        subject: str,
        items: Sequence[SitePriceRequest],
    ) -> Sequence[SitePrice]:
        prices: list[SitePrice] = []

        for start in range(0, len(items), MAX_PRICED_ITEMS):
            chunk = items[start : start + MAX_PRICED_ITEMS]
            try:
                response = await self._client.post(
                    "me/prices",
                    {
                        "items": [
                            {
                                "id": item.product_id.value,
                                "quantity": str(item.quantity.value),
                            }
                            for item in chunk
                        ],
                    },
                    customer=subject,
                )
            except SiteApiError as e:
                reraise_common(e, "me/prices")

            prices.extend(_price(entry) for entry in as_list(response.data, "prices"))

        return prices


def _price(entry: object) -> SitePrice:
    """One answered position; unavailable ones carry a reason and no price."""
    document = as_object(entry, "a price")
    product_id = ProductId(value=text(document, "id"))
    price = document.get("price")

    if not flag(document, "available") or price is None:
        return SitePrice(
            product_id=product_id,
            unit_price=None,
            reason=optional_text(document, "reason") or "unavailable",
        )

    price_document = as_object(price, "a price")
    unit_price = money(price_document, "amount", price_document.get("currency"))
    return SitePrice(
        product_id=product_id,
        unit_price=unit_price,
        reason=None if unit_price is not None else "no_price",
    )


class HttpSiteFinance(SiteFinance):
    """``GET /me/finance/summary`` — the top of the site's finance page."""

    def __init__(self, client: SiteApiClient) -> None:
        self._client: Final[SiteApiClient] = client

    @override
    async def summary(self, subject: str) -> SiteFinanceSummaryView:
        try:
            response = await self._client.get("me/finance/summary", customer=subject)
        except SiteApiError as e:
            if isinstance(e, SiteApiRejectedError) and e.code == "finance_denied":
                reason = e.details.get("reason")
                msg = "The site will not show this customer the company's money."
                raise SiteFinanceDeniedError(
                    msg,
                    reason=reason if isinstance(reason, str) else "denied",
                ) from e
            if e.code == "erp_not_configured":
                msg = "The site has no bridge to 1C configured."
                raise SiteFinanceDeniedError(msg, reason="not_configured") from e
            reraise_common(e, "me/finance/summary")

        return _summary(as_object(response.data, "a summary"), response.meta)


def _summary(data: object, meta: object) -> SiteFinanceSummaryView:
    """The summary document and its ``meta.erp`` freshness, as one view.

    Amounts become views directly, without passing through ``Money``: a
    balance from 1C may be negative, and this is a report to show, not a price
    anybody will be charged.
    """
    document = as_object(data, "a summary")
    erp = as_object(as_object(meta, "meta").get("erp") or {}, "meta.erp")

    company = document.get("company")
    debt = document.get("debt")
    overdue = document.get("overdue")
    limit = document.get("credit_limit")

    total = (
        None if debt is None else as_object(as_object(debt, "debt").get("total"), "total")
    )
    currency_code = (
        "RUB" if total is None else (optional_text(total, "currency") or "RUB")
    )
    overdue_document = None if overdue is None else as_object(overdue, "overdue")
    limit_document = None if limit is None else as_object(limit, "credit_limit")

    def amount(source: Mapping[str, object] | None, key: str) -> MoneyView | None:
        value = None if source is None else decimal(source, key)
        return (
            None
            if value is None
            else MoneyView(
                amount=value.quantize(Decimal("0.01")),
                currency=currency_code.lower(),
            )
        )

    return SiteFinanceSummaryView(
        company_name=None
        if company is None
        else optional_text(as_object(company, "company"), "name"),
        erp_linked=erp.get("source") != "none",
        debt=amount(total, "debt"),
        advance=amount(total, "advance"),
        overdue=amount(overdue_document, "total_overdue"),
        max_days_overdue=None
        if overdue_document is None
        else optional_integer(overdue_document, "max_days_overdue"),
        credit_limit=amount(limit_document, "amount"),
        credit_available=amount(limit_document, "available"),
        as_of=moment(erp, "as_of"),
        is_stale=flag(erp, "stale"),
        is_partial=flag(erp, "partial"),
    )
