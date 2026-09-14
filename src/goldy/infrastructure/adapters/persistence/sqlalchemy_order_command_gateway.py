import logging
from typing import TYPE_CHECKING, Final, override

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.entities.order import Order
from goldy.infrastructure.errors import RepoError

if TYPE_CHECKING:
    from goldy.domain.orders.values.order_id import OrderId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyOrderCommandGateway(OrderCommandGateway):
    """Loads and stores whole :class:`Order` aggregates, lines included.

    The lines come with the order because every rule this side enforces is
    about the order as a whole, and because ``Order.total`` is derived from the
    lines each time it is asked for: an order loaded without them would report
    a total of nothing and nothing would fail. The mapping fetches them with
    ``selectin``, so that is one extra round trip and no cartesian product.

    Every aggregate handed back gets the request-scoped ``EventsCollection``
    injected. It is not a column, SQLAlchemy leaves it unset on a loaded
    instance, and an order genuinely records events — so without the injection
    the first confirmation would fail on a missing attribute, a long way from
    the read that actually caused it.
    """

    def __init__(
        self,
        session: AsyncSession,
        events_collection: EventsCollection,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._events_collection: Final[EventsCollection] = events_collection

    @override
    async def add(self, order: Order) -> None:
        """Inserts the order with its lines, flushing so a failure lands here.

        Unlike a registration, there is no losing race to translate. The number
        comes from a sequence that never yields one value twice, so the unique
        index on it guards against a hand-typed insert rather than against a
        concurrent checkout: hitting it means a defect, and there is nothing to
        retry. The flush is kept all the same, so a refusal is reported by the
        gateway that knows which order it was about instead of surfacing later,
        out of the transaction pipeline, as a commit that did not happen.

        Raises:
            RepoError: the order could not be written.
        """
        self._session.add(order)

        try:
            await self._session.flush()
        except SQLAlchemyError as e:
            logger.exception("failed to add the order %s", order.id)
            msg = f"Failed to add order '{order.number}'."
            raise RepoError(msg) from e

    @override
    async def by_id(self, order_id: OrderId) -> Order | None:
        """The whole order, ready to be acted on.

        Raises:
            RepoError: the order could not be read.
        """
        try:
            order = await self._session.get(Order, order_id)
        except SQLAlchemyError as e:
            logger.exception("failed to read the order by id")
            msg = "Failed to read the order by id."
            raise RepoError(msg) from e

        if order is None:
            return None

        order.events_collection = self._events_collection
        return order
