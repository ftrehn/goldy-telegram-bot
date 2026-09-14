import logging
from typing import TYPE_CHECKING, Final, override

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.error import CartAlreadyExistsError
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.common.events_collection import EventsCollection
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models import carts_table

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyCartCommandGateway(CartCommandGateway):
    """Loads and stores whole :class:`Cart` aggregates, the way the user gateway does.

    Every aggregate handed back gets the request-scoped ``EventsCollection``
    injected, exactly as ``SqlAlchemyUserCommandGateway`` does and for exactly
    the same reason: it is not a column, so SQLAlchemy leaves it unset on a
    loaded instance, and the first method that records an event would fail on
    a missing attribute far from the load that caused it.

    Thin on purpose. Whether a person without a cart should get one is not a
    question about rows, and it is answered by ``CartProvider`` in the
    application layer; this class inserts what it is handed and says when the
    unique index on ``user_id`` refused it.
    """

    def __init__(
        self,
        session: AsyncSession,
        events_collection: EventsCollection,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._events_collection: Final[EventsCollection] = events_collection

    @override
    async def add(self, cart: Cart) -> None:
        """Inserts a new cart inside a savepoint, flushing so a clash surfaces here.

        The savepoint is the difference from ``SqlAlchemyUserCommandGateway``.
        A refused insert outside one leaves the session rollback-only, and the
        caller's next move after a clash is to *read* the cart that won — a
        read a rollback-only session refuses with ``PendingRollbackError``.
        Rolled back to the savepoint, the session carries on, and the pending
        aggregate is expunged with it.

        Raises:
            CartAlreadyExistsError: this person already has a cart.
            RepoError: the insert failed for any other reason.
        """
        try:
            async with self._session.begin_nested():
                self._session.add(cart)
                await self._session.flush()
        except IntegrityError as e:
            logger.info("cart already exists for user %s", cart.user_id)
            msg = f"User '{cart.user_id}' already has a cart."
            raise CartAlreadyExistsError(msg) from e
        except SQLAlchemyError as e:
            logger.exception("failed to add the cart")
            msg = "Failed to add the cart."
            raise RepoError(msg) from e

    @override
    async def by_user_id(self, user_id: UserId) -> Cart | None:
        stmt = select(Cart).where(carts_table.c.user_id == user_id)

        try:
            cart = (await self._session.execute(stmt)).scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the cart by user id")
            msg = "Failed to read the cart by user id."
            raise RepoError(msg) from e

        if cart is not None:
            cart.events_collection = self._events_collection

        return cart
