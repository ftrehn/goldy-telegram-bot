from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from goldy.domain.orders.values.order_id import OrderId

if TYPE_CHECKING:
    from goldy.application.common.ports.site.site_orders import SiteOrderStatus


class HandoverState(StrEnum):
    """How far handing one order over to the site has got.

    ``PENDING`` — waiting for its turn or for the next attempt. ``ACCEPTED`` —
    the site made an order of it, and statuses now come from there.
    ``REJECTED`` — the site refused it, and asking again gets the same answer.
    ``WITHDRAWN`` — the customer cancelled before it was handed over, so there
    is nothing to hand.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True, slots=True)
class OrderHandover:
    """One order's handover record, as the handlers read it."""

    order_id: OrderId
    state: HandoverState
    attempts: int
    site_order_id: int | None
    site_number: str | None
    error_code: str | None


class OrderHandoverDao(Protocol):
    """The record of which orders the site has, and which it still has to get.

    A DAO rather than a gateway: it schedules idempotently, locks, picks the
    due rows and marks outcomes, and there is no aggregate behind it. The
    handover is the state of an integration — the thing ``Order`` refuses to
    carry — so it lives beside the order in a table of its own.

    Scheduling is the outbox's consumer end, and ``schedule`` is the whole of
    its idempotency: a second delivery of the same ``OrderPlaced`` inserts
    nothing, because the order id is the primary key.
    """

    @abstractmethod
    async def schedule(self, order_id: OrderId) -> bool:
        """Puts the order in the queue. False when it was already there."""
        raise NotImplementedError

    @abstractmethod
    async def lock(self, order_id: OrderId) -> OrderHandover | None:
        """Reads the record and holds it until the transaction ends.

        The handover and the customer's cancellation both take this lock, so
        an order is never handed over in the moment it is being withdrawn.
        """
        raise NotImplementedError

    @abstractmethod
    async def due(self, limit: int) -> Sequence[OrderId]:
        """Pending orders whose next attempt is due, oldest first."""
        raise NotImplementedError

    @abstractmethod
    async def mark_accepted(self, order_id: OrderId, status: SiteOrderStatus) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_retry(self, order_id: OrderId, delay: timedelta, error: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_rejected(self, order_id: OrderId, code: str, error: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_withdrawn(self, order_id: OrderId) -> None:
        raise NotImplementedError

    @abstractmethod
    async def record_site_status(self, status: SiteOrderStatus) -> bool:
        """Stores the site's latest word on an accepted order.

        False when there is no accepted handover for ``external_id`` — the
        feed is the site's whole list for this client, and an order the bot
        did not hand over, or one it no longer has, is not its business.
        """
        raise NotImplementedError

    @abstractmethod
    async def latest_site_update(self) -> datetime | None:
        """The newest ``updated_at`` the feed has delivered so far, if any."""
        raise NotImplementedError
