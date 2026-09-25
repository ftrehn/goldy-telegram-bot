import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Final

from goldy.application.commands.site.apply_site_order_status.command import (
    ApplySiteOrderStatusCommand,
)
from goldy.application.commands.site.hand_over_order.command import (
    HandOverOrderCommand,
    HandoverOutcome,
)
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.site import OrderHandoverDao, SiteOrders

logger: Final[logging.Logger] = logging.getLogger(__name__)

HANDOVER_BATCH: Final[int] = 20
"""How many due orders one tick hands over. The rest wait for the next minute.

The site takes twenty orders a minute from one client, so a bigger batch
would only collect ``rate_limited`` refusals and push every order behind it
into the growing retry delay.
"""

FEED_OVERLAP: Final[timedelta] = timedelta(minutes=5)
"""How far back from the newest change seen the next feed pass starts.

The feed is ordered by the site's update time, and two orders updated in the
same second can land on either side of the page a pass stopped on. Reading a
few minutes twice costs nothing — applying a status is idempotent — while a
gap would lose a cancellation.
"""


class OrderHandoverRunner:
    """One tick of handing orders to the site and of reading their statuses back.

    Not a command, for the reason ``CatalogSynchronizer`` is not one: every
    order is handed over in a transaction of its own, committed as it goes, so
    one order the site refuses does not roll back the ones before it. Each
    command still goes through the transaction and events pipelines.

    Two ticks may overlap across workers without harm. The handover locks the
    order's row and skips anything no longer pending; the site takes an order
    once per ``external_id`` whatever happens; and applying a status only ever
    moves an order forward.
    """

    def __init__(
        self,
        sender: Sender,
        order_handover_dao: OrderHandoverDao,
        site_orders: SiteOrders,
    ) -> None:
        self._sender: Final[Sender] = sender
        self._order_handover_dao: Final[OrderHandoverDao] = order_handover_dao
        self._site_orders: Final[SiteOrders] = site_orders

    async def hand_over_due(self) -> Counter[HandoverOutcome]:
        """Hands over the orders whose turn has come; counts what happened."""
        outcomes: Counter[HandoverOutcome] = Counter()

        for order_id in await self._order_handover_dao.due(HANDOVER_BATCH):
            outcomes[
                await self._sender.send(HandOverOrderCommand(order_id=order_id))
            ] += 1

        if outcomes:
            logger.info("site handover: %s", dict(outcomes))

        return outcomes

    async def pull_statuses(self) -> int:
        """Applies every change the site's feed has since the last one seen.

        Nothing to ask while no order was ever accepted — the feed is this
        client's, and a client that handed nothing over has nothing in it.

        Raises:
            SiteUnavailableError: the site did not answer; the next tick
                starts from the same place.
        """
        latest = await self._order_handover_dao.latest_site_update()

        if latest is None:
            return 0

        since = min(latest, datetime.now(UTC)) - FEED_OVERLAP
        moved = 0

        async for page in self._site_orders.changes(since):
            for status in page:
                if await self._sender.send(ApplySiteOrderStatusCommand(status=status)):
                    moved += 1

        if moved:
            logger.info("site feed: %d order(s) moved", moved)

        return moved
