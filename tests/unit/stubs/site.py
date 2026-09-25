"""Stand-ins for the site's ports (ADR-0004), for the handlers' tests.

Not transports: the handlers talk to ports, and what a handler test asks is
what the handler does with an answer or a refusal — the HTTP translation has
its own tests against real ``httpx`` responses.

Each stub records what it was asked and answers from what the test put in
it; an exception placed in a queue is raised in place of the next answer.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import cast, final, override

from goldy.application.commands.site.apply_site_order_status.command import (
    ApplySiteOrderStatusCommand,
)
from goldy.application.commands.site.apply_site_order_status.handler import (
    ApplySiteOrderStatusHandler,
)
from goldy.application.commands.site.hand_over_order.command import HandOverOrderCommand
from goldy.application.commands.site.hand_over_order.handler import HandOverOrderHandler
from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.site import (
    HandoverState,
    OrderHandover,
    OrderHandoverDao,
    SiteCustomer,
    SiteLinkRequest,
    SiteLinking,
    SiteOrderState,
    SiteOrderStatus,
    SiteOrderSubmission,
    SiteOrders,
    SitePrice,
    SitePriceRequest,
    SitePricing,
)
from goldy.application.common.ports.users import SiteLinkQueryGateway
from goldy.application.common.views.site import SiteLinkPreviewView, SiteLinkView
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.money import Money
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.user_id import UserId


def site_link_view(
    *,
    customer_name: str = "Иван Иванов",
    company_name: str | None = "ТД «Ромашка»",
    is_wholesale: bool = True,
) -> SiteLinkView:
    """A linked person, as the bot's copy of the link reads."""
    return SiteLinkView(
        customer_name=customer_name,
        company_name=company_name,
        is_wholesale=is_wholesale,
        linked_at=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
    )


@final
class InMemorySiteLinkQueryGateway(SiteLinkQueryGateway):
    """Links by user id, as a dictionary a test fills in."""

    def __init__(self, links: dict[UserId, SiteLinkView] | None = None) -> None:
        self.links: dict[UserId, SiteLinkView] = dict(links or {})

    @override
    async def read_for(self, user_id: UserId) -> SiteLinkView | None:
        return self.links.get(user_id)


@final
class ScriptedSitePricing(SitePricing):
    """Answers every product from ``prices``; unknown ones come back unavailable."""

    def __init__(self, prices: dict[ProductId, Money | None] | None = None) -> None:
        self.prices: dict[ProductId, Money | None] = dict(prices or {})
        self.errors: list[Exception] = []
        self.calls: list[tuple[str, list[SitePriceRequest]]] = []

    @override
    async def prices_for(
        self,
        subject: str,
        items: Sequence[SitePriceRequest],
    ) -> Sequence[SitePrice]:
        self.calls.append((subject, list(items)))

        if self.errors:
            raise self.errors.pop(0)

        return [
            SitePrice(
                product_id=item.product_id,
                unit_price=self.prices.get(item.product_id),
                reason=None if self.prices.get(item.product_id) else "unknown",
            )
            for item in items
        ]


@final
class ScriptedSiteLinking(SiteLinking):
    """Previews, confirms and revokes from queues a test fills in."""

    def __init__(self) -> None:
        self.preview_answer = SiteLinkPreviewView(
            customer_name="Иван И.",
            email="i***@example.ru",
            company_name="ТД «Ромашка»",
        )
        self.customer = SiteCustomer(
            name="Иван Иванов",
            company_name="ТД «Ромашка»",
            is_wholesale=True,
            finance_access=True,
        )
        self.errors: list[Exception] = []
        self.revoke_errors: list[Exception] = []
        self.previews: list[tuple[str, MessengerPlatform]] = []
        self.confirmations: list[SiteLinkRequest] = []
        self.revoked: list[str] = []

    @override
    async def preview(
        self, code: str, platform: MessengerPlatform
    ) -> SiteLinkPreviewView:
        self.previews.append((code, platform))

        if self.errors:
            raise self.errors.pop(0)

        return self.preview_answer

    @override
    async def confirm(self, request: SiteLinkRequest) -> SiteCustomer:
        self.confirmations.append(request)

        if self.errors:
            raise self.errors.pop(0)

        return self.customer

    @override
    async def revoke(self, subject: str) -> None:
        self.revoked.append(subject)

        if self.revoke_errors:
            raise self.revoke_errors.pop(0)


def site_order_status(
    external_id: str,
    *,
    state: str = "new",
    site_order_id: int = 1234,
    updated_at: datetime | None = None,
) -> SiteOrderStatus:
    """An order as the site describes it."""
    return SiteOrderStatus(
        external_id=external_id,
        site_order_id=site_order_id,
        number=str(site_order_id),
        status_code="N",
        status_name="Принят",
        state=SiteOrderState(state),
        updated_at=updated_at or datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
    )


@final
class ScriptedSiteOrders(SiteOrders):
    """Takes orders, cancels them and serves a feed, from what a test put in."""

    def __init__(self) -> None:
        self.submit_errors: list[Exception] = []
        self.cancel_errors: list[Exception] = []
        self.feed_pages: list[list[SiteOrderStatus]] = []
        self.feed_error: Exception | None = None
        self.submitted: list[SiteOrderSubmission] = []
        self.cancelled: list[tuple[str, str | None, str | None]] = []
        self.feed_since: list[datetime] = []

    @override
    async def submit(self, submission: SiteOrderSubmission) -> SiteOrderStatus:
        self.submitted.append(submission)

        if self.submit_errors:
            raise self.submit_errors.pop(0)

        return site_order_status(submission.external_id)

    @override
    async def cancel(
        self,
        external_id: str,
        subject: str | None,
        reason: str | None,
    ) -> SiteOrderStatus:
        self.cancelled.append((external_id, subject, reason))

        if self.cancel_errors:
            raise self.cancel_errors.pop(0)

        return site_order_status(external_id, state="cancelled")

    @override
    async def changes(self, since: datetime) -> AsyncIterator[Sequence[SiteOrderStatus]]:
        self.feed_since.append(since)

        for page in self.feed_pages:
            yield page

        if self.feed_error is not None:
            raise self.feed_error


@dataclass
class HandoverRecord:
    """One row of the in-memory handover table."""

    state: HandoverState = HandoverState.PENDING
    attempts: int = 0
    next_attempt_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_code: str | None = None
    last_error: str | None = None
    site: SiteOrderStatus | None = None
    locked: bool = False


@final
class InMemoryOrderHandoverDao(OrderHandoverDao):
    """The handover table as a dictionary, with the same rules as the real one."""

    def __init__(self) -> None:
        self.rows: dict[OrderId, HandoverRecord] = {}

    @override
    async def schedule(self, order_id: OrderId) -> bool:
        if order_id in self.rows:
            return False

        self.rows[order_id] = HandoverRecord()
        return True

    @override
    async def lock(self, order_id: OrderId) -> OrderHandover | None:
        row = self.rows.get(order_id)

        if row is None:
            return None

        row.locked = True
        return OrderHandover(
            order_id=order_id,
            state=row.state,
            attempts=row.attempts,
            site_order_id=None if row.site is None else row.site.site_order_id,
            site_number=None if row.site is None else row.site.number,
            error_code=row.error_code,
        )

    @override
    async def due(self, limit: int) -> Sequence[OrderId]:
        now = datetime.now(UTC)
        due = [
            order_id
            for order_id, row in self.rows.items()
            if row.state is HandoverState.PENDING and row.next_attempt_at <= now
        ]
        return due[:limit]

    @override
    async def mark_accepted(self, order_id: OrderId, status: SiteOrderStatus) -> None:
        row = self.rows[order_id]
        row.state = HandoverState.ACCEPTED
        row.attempts += 1
        row.site = status

    @override
    async def mark_retry(self, order_id: OrderId, delay: timedelta, error: str) -> None:
        row = self.rows[order_id]
        row.attempts += 1
        row.next_attempt_at = datetime.now(UTC) + delay
        row.last_error = error

    @override
    async def mark_rejected(self, order_id: OrderId, code: str, error: str) -> None:
        row = self.rows[order_id]
        row.state = HandoverState.REJECTED
        row.attempts += 1
        row.error_code = code
        row.last_error = error

    @override
    async def mark_withdrawn(self, order_id: OrderId) -> None:
        self.rows[order_id].state = HandoverState.WITHDRAWN

    @override
    async def record_site_status(self, status: SiteOrderStatus) -> bool:
        for order_id, row in self.rows.items():
            if (
                str(order_id) == status.external_id
                and row.state is HandoverState.ACCEPTED
            ):
                row.site = replace(status)
                return True
        return False

    @override
    async def latest_site_update(self) -> datetime | None:
        stamps = [
            row.site.updated_at
            for row in self.rows.values()
            if row.site is not None and row.site.updated_at is not None
        ]
        return max(stamps, default=None)


@final
class HandoverCommandSender(Sender):
    """Runs the two handover commands through their real handlers, in order.

    For ``OrderHandoverRunner``'s own tests: the runner sends commands rather
    than calling a handler directly, so what "one command per due order" and
    "moved orders are counted" need is the real handlers' answers together with
    the list of requests the runner actually made.
    """

    def __init__(
        self,
        hand_over_handler: HandOverOrderHandler,
        apply_status_handler: ApplySiteOrderStatusHandler,
    ) -> None:
        self._hand_over_handler = hand_over_handler
        self._apply_status_handler = apply_status_handler
        self.requests: list[BaseRequest[object]] = []

    @override
    async def send[TResponse](self, request: BaseRequest[TResponse]) -> TResponse:
        self.requests.append(request)

        if isinstance(request, HandOverOrderCommand):
            return cast("TResponse", await self._hand_over_handler.handle(request))

        if isinstance(request, ApplySiteOrderStatusCommand):
            return cast("TResponse", await self._apply_status_handler.handle(request))

        msg = f"{type(request).__name__} is not a handover command."
        raise AssertionError(msg)
