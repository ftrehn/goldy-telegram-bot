import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, override

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.carts import CartCommandGateway
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.carts.ports.id_generator import CartIdGenerator
from goldy.domain.common.events_collection import EventsCollection
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models import carts_table

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyCartCommandGateway(CartCommandGateway):
    """Loads whole :class:`Cart` aggregates and lets the session store them.

    Every aggregate handed back gets the request-scoped ``EventsCollection``
    injected, exactly as ``SqlAlchemyUserCommandGateway`` does and for exactly
    the same reason: it is not a column, so SQLAlchemy leaves it unset on a
    loaded instance. The cart records no events today, which makes skipping the
    injection look free — it is not. The first method somebody makes
    event-recording would fail on a missing attribute, far from the load that
    caused it.

    There is no ``add``. An aggregate returned from here is attached to the
    session, so the lines a command adds or removes are written out when the
    transaction pipeline commits; a separate save would be a second way to do
    what the unit of work already does.
    """

    def __init__(
        self,
        session: AsyncSession,
        events_collection: EventsCollection,
        cart_id_generator: CartIdGenerator,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._events_collection: Final[EventsCollection] = events_collection
        self._cart_id_generator: Final[CartIdGenerator] = cart_id_generator

    @override
    async def ensure_for(self, user_id: UserId) -> Cart:
        """Reads this person's cart, inserting one if they have none.

        Read, then ``INSERT ... ON CONFLICT (user_id) DO NOTHING``, then read
        again. "One cart per person" spans two aggregates, so the unique index
        on ``carts.user_id`` is what actually holds it — two simultaneous first
        additions both find nothing and both insert, and the loser must not be
        told anything went wrong.

        ``DO NOTHING`` rather than an insert whose ``IntegrityError`` is caught:
        after an integrity failure the session is rollback-only, so the second
        read — the whole point of the retry — would die on
        ``PendingRollbackError`` instead.

        The row is written in Core and the aggregate read back through the ORM
        on purpose. What the caller gets is then a session-attached instance
        whose lines are flushed at commit, rather than a detached object the
        unit of work knows nothing about.

        Raises:
            RepoError: the row was neither found nor inserted, which under read
                committed means the database is not behaving as this method
                requires.
        """
        cart = await self.by_user_id(user_id)

        if cart is not None:
            return cart

        await self._insert_row(user_id)
        cart = await self.by_user_id(user_id)

        if cart is None:
            logger.error("cart for user %s neither found nor inserted", user_id)
            msg = f"Failed to obtain a cart for user '{user_id}'."
            raise RepoError(msg)

        return cart

    @override
    async def by_user_id(self, user_id: UserId) -> Cart | None:
        stmt = select(Cart).where(carts_table.c.user_id == user_id)

        try:
            cart = (await self._session.execute(stmt)).scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the cart by user id")
            msg = "Failed to read the cart by user id."
            raise RepoError(msg) from e

        return self._inject(cart) if cart is not None else None

    async def _insert_row(self, user_id: UserId) -> None:
        """Writes the row, or leaves the one a concurrent request wrote alone.

        The timestamps are stamped here rather than taken from a freshly built
        aggregate, because the aggregate built to carry them would be thrown
        away unread: the cart the caller gets comes from the read that follows.
        Both columns say the same thing ``Entity`` says by default — the row
        was created now and has not been touched since.
        """
        now = datetime.now(UTC)
        stmt = (
            postgresql_insert(carts_table)
            .values(
                id=self._cart_id_generator(),
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[carts_table.c.user_id])
        )

        try:
            await self._session.execute(stmt)
        except SQLAlchemyError as e:
            logger.exception("failed to insert the cart")
            msg = "Failed to insert the cart."
            raise RepoError(msg) from e

    def _inject(self, cart: Cart) -> Cart:
        cart.events_collection = self._events_collection
        return cart
