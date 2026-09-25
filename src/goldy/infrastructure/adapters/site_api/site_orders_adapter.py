from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Final, NoReturn, override
from urllib.parse import quote

from goldy.application.common.ports.site import (
    SiteOrderState,
    SiteOrderStatus,
    SiteOrderSubmission,
    SiteOrders,
)
from goldy.application.error import (
    SiteOrderNotCancellableError,
    SiteOrderRejectedError,
)
from goldy.infrastructure.adapters.site_api.site_api_client import SiteApiClient
from goldy.infrastructure.adapters.site_api.site_documents import (
    CUSTOMER_NOT_LINKED,
    as_list,
    as_object,
    integer,
    moment,
    reraise_common,
    text,
)
from goldy.infrastructure.errors import (
    SiteApiError,
    SiteApiRejectedError,
    SiteApiResponseError,
)

_NOT_REFUSALS: Final[frozenset[str | None]] = frozenset(
    {None, "unauthorized", "scope_required", "api_disabled", CUSTOMER_NOT_LINKED},
)
"""4xx codes that say nothing about the order: a token, a scope, a stale link.

A refusal without a code at all is here too — the site always sends one, so a
4xx without it came from something in front of the site, not from the site's
opinion of the order.
"""

FEED_PAGE_SIZE: Final[int] = 100
"""The site gives at most a hundred orders per page of its feed."""


def _amount(value: Decimal) -> str:
    """Money the way the site takes it: a string with two decimals."""
    return f"{value.quantize(Decimal('0.01'))}"


def _status(document: object) -> SiteOrderStatus:
    """One order as the site describes it, in any of its answers."""
    order = as_object(document, "an order")
    status = as_object(order.get("status"), "an order status")
    state_value = text(status, "state")

    try:
        state = SiteOrderState(state_value)
    except ValueError as e:
        msg = f"The site sent order state {state_value!r}, which is not the contract."
        raise SiteApiResponseError(msg) from e

    return SiteOrderStatus(
        external_id=text(order, "external_id"),
        site_order_id=integer(order, "site_order_id"),
        number=text(order, "number"),
        status_code=text(status, "code"),
        status_name=text(status, "name"),
        state=state,
        updated_at=moment(order, "updated_at"),
    )


class HttpSiteOrders(SiteOrders):
    """``POST /orders``, ``POST /orders/{id}/cancel`` and the ``GET /orders`` feed.

    Every refusal of an order is one error with the site's code on it: prices
    moved, a position is gone, the credit limit is used up, the ``external_id``
    names a different order. The handover records the code for a person to
    read and does not ask again — the same order gets the same answer. The
    only refusals kept apart are the site forgetting the customer (the link
    is stale) and an outage, both of which the caller treats differently.
    """

    def __init__(self, client: SiteApiClient) -> None:
        self._client: Final[SiteApiClient] = client

    @override
    async def submit(self, submission: SiteOrderSubmission) -> SiteOrderStatus:
        body: dict[str, object] = {
            "external_id": submission.external_id,
            "number": submission.number,
            "items": [
                {
                    "id": item.product_id.value,
                    "quantity": str(item.quantity),
                    "price": _amount(item.unit_price),
                }
                for item in submission.items
            ],
            "expected_total": _amount(submission.expected_total),
            "recipient": {
                "name": submission.recipient_name,
                "phone": submission.recipient_phone,
            },
            "delivery": {"address": submission.address},
            "comment": submission.comment,
        }

        try:
            response = await self._client.post(
                "orders",
                body,
                customer=submission.subject,
            )
        except SiteApiError as e:
            self._reraise_refusal(e, "orders")

        return _status(response.data)

    @override
    async def cancel(
        self,
        external_id: str,
        subject: str | None,
        reason: str | None,
    ) -> SiteOrderStatus:
        path = f"orders/{quote(external_id, safe='')}/cancel"
        body: dict[str, object] = {} if reason is None else {"reason": reason}

        try:
            response = await self._client.post(path, body, customer=subject)
        except SiteApiError as e:
            if isinstance(e, SiteApiRejectedError) and e.code == "order_not_cancellable":
                msg = "The site will not let the customer cancel this order any more."
                raise SiteOrderNotCancellableError(msg) from e
            self._reraise_refusal(e, "orders/{id}/cancel")

        return _status(response.data)

    @override
    async def changes(self, since: datetime) -> AsyncIterator[Sequence[SiteOrderStatus]]:
        params: Mapping[str, str | int] = {"updated_since": since.isoformat()}

        try:
            async for page in self._client.paginate(
                "orders",
                limit=FEED_PAGE_SIZE,
                params=params,
            ):
                yield [_status(entry) for entry in as_list(page.data, "the order feed")]
        except SiteApiError as e:
            reraise_common(e, "orders feed")

    @staticmethod
    def _reraise_refusal(error: SiteApiError, where: str) -> NoReturn:
        """Any 4xx but a stale link is the site refusing this order.

        Raises:
            SiteOrderRejectedError: the site refused the order itself.
            SiteCustomerNotLinkedError: the subject is not linked any more.
            SiteUnavailableError: the site did not answer.
            SiteApiError: a bad token or scope — configuration, not the order.
        """
        if isinstance(error, SiteApiRejectedError) and error.code not in _NOT_REFUSALS:
            msg = f"The site refused the order at {where}: {error.code or error.status}."
            raise SiteOrderRejectedError(
                msg, code=error.code or str(error.status)
            ) from error

        reraise_common(error, where)
