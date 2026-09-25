from abc import abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from goldy.domain.catalog.values.product_id import ProductId


class SiteOrderState(StrEnum):
    """The site's condensed order state, as its API names it.

    Four values for clients that have no statuses of their own; the site's
    own code and name travel beside it in :class:`SiteOrderStatus`.
    """

    NEW = "new"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SiteOrderStatus:
    """Where the order the bot handed over stands on the site.

    ``external_id`` is the bot's ``OrderId`` as text — the key both sides
    share. ``updated_at`` is the site's clock, and it is what the next pass of
    the order feed asks "changed since" against.
    """

    external_id: str
    site_order_id: int
    number: str
    status_code: str
    status_name: str
    state: SiteOrderState
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class SiteOrderItem:
    """One order line as the site takes it: position, quantity, the price shown."""

    product_id: ProductId
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True, slots=True)
class SiteOrderSubmission:
    """A bot order in the shape ``POST /orders`` takes.

    ``subject`` is set when the customer is linked to the site: the order then
    lands on their site account and is priced by their terms, which is what
    the prices in :attr:`items` already are. Without it the site takes the
    order as a guest's, at retail.
    """

    external_id: str
    number: str
    subject: str | None
    items: Sequence[SiteOrderItem]
    expected_total: Decimal
    recipient_name: str
    recipient_phone: str
    address: str | None
    comment: str | None


class SiteOrders(Protocol):
    """Hands orders over to the site, reads their statuses back, cancels them."""

    @abstractmethod
    async def submit(self, submission: SiteOrderSubmission) -> SiteOrderStatus:
        """Hands the order over. Repeating it returns the order already made.

        Raises:
            SiteOrderRejectedError: the site refused the order itself.
            SiteCustomerNotLinkedError: the site no longer knows the subject.
            SiteUnavailableError: the site did not answer.
        """
        raise NotImplementedError

    @abstractmethod
    async def cancel(
        self,
        external_id: str,
        subject: str | None,
        reason: str | None,
    ) -> SiteOrderStatus:
        """Cancels on the customer's behalf. Cancelling twice is not an error.

        Raises:
            SiteOrderNotCancellableError: the order is in work or paid.
            SiteOrderRejectedError: the site does not know the order.
            SiteUnavailableError: the site did not answer.
        """
        raise NotImplementedError

    @abstractmethod
    def changes(self, since: datetime) -> AsyncIterator[Sequence[SiteOrderStatus]]:
        """The site's order feed from ``since`` on, page by page.

        Raises:
            SiteUnavailableError: the site did not answer.
        """
        raise NotImplementedError
