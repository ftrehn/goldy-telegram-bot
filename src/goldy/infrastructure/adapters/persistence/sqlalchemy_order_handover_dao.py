import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, final, override
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.site import (
    HandoverState,
    OrderHandover,
    OrderHandoverDao,
)
from goldy.domain.orders.values.order_id import OrderId
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models import order_handovers_table

if TYPE_CHECKING:
    from goldy.application.common.ports.site import SiteOrderStatus

logger: Final[logging.Logger] = logging.getLogger(__name__)

MAX_ERROR_LENGTH: Final[int] = 2000


@final
class SqlAlchemyOrderHandoverDao(OrderHandoverDao):
    """Rows of ``order_handovers``, written with Core statements.

    ``schedule`` is an insert inside a savepoint and the primary key deciding,
    the way the inbox claims a message: portable, and it leaves the caller's
    transaction usable after a refused insert. ``lock`` is ``SELECT … FOR
    UPDATE``, which is the one thing that keeps a handover and a cancellation
    of the same order from interleaving.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def schedule(self, order_id: OrderId) -> bool:
        now = datetime.now(UTC)
        statement = insert(order_handovers_table).values(
            order_id=order_id,
            state=HandoverState.PENDING.value,
            attempts=0,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )

        try:
            async with self._session.begin_nested():
                await self._session.execute(statement)
        except IntegrityError:
            return False
        except SQLAlchemyError as e:
            msg = f"Failed to schedule the handover of order {order_id}."
            raise RepoError(msg) from e

        return True

    @override
    async def lock(self, order_id: OrderId) -> OrderHandover | None:
        statement = (
            select(order_handovers_table)
            .where(order_handovers_table.c.order_id == order_id)
            .with_for_update()
        )
        try:
            row = (await self._session.execute(statement)).mappings().one_or_none()
        except SQLAlchemyError as e:
            msg = f"Failed to lock the handover of order {order_id}."
            raise RepoError(msg) from e

        if row is None:
            return None

        return OrderHandover(
            order_id=OrderId(row["order_id"]),
            state=HandoverState(row["state"]),
            attempts=row["attempts"],
            site_order_id=row["site_order_id"],
            site_number=row["site_number"],
            error_code=row["error_code"],
        )

    @override
    async def due(self, limit: int) -> Sequence[OrderId]:
        statement = (
            select(order_handovers_table.c.order_id)
            .where(
                order_handovers_table.c.state == HandoverState.PENDING.value,
                order_handovers_table.c.next_attempt_at <= datetime.now(UTC),
            )
            .order_by(order_handovers_table.c.next_attempt_at)
            .limit(limit)
        )

        try:
            ids = (await self._session.execute(statement)).scalars().all()
        except SQLAlchemyError as e:
            msg = "Failed to read the due order handovers."
            raise RepoError(msg) from e

        return [OrderId(value) for value in ids]

    @override
    async def mark_accepted(self, order_id: OrderId, status: SiteOrderStatus) -> None:
        await self._update(
            order_id,
            state=HandoverState.ACCEPTED.value,
            attempts=order_handovers_table.c.attempts + 1,
            error_code=None,
            last_error=None,
            **self._site_columns(status),
        )

    @override
    async def mark_retry(self, order_id: OrderId, delay: timedelta, error: str) -> None:
        await self._update(
            order_id,
            attempts=order_handovers_table.c.attempts + 1,
            next_attempt_at=datetime.now(UTC) + delay,
            last_error=error[:MAX_ERROR_LENGTH],
        )

    @override
    async def mark_rejected(self, order_id: OrderId, code: str, error: str) -> None:
        await self._update(
            order_id,
            state=HandoverState.REJECTED.value,
            attempts=order_handovers_table.c.attempts + 1,
            error_code=code[:64],
            last_error=error[:MAX_ERROR_LENGTH],
        )

    @override
    async def mark_withdrawn(self, order_id: OrderId) -> None:
        await self._update(order_id, state=HandoverState.WITHDRAWN.value)

    @override
    async def record_site_status(self, status: SiteOrderStatus) -> bool:
        try:
            order_id = UUID(status.external_id)
        except ValueError:
            return False

        statement = (
            update(order_handovers_table)
            .where(
                order_handovers_table.c.order_id == order_id,
                order_handovers_table.c.state == HandoverState.ACCEPTED.value,
            )
            .values(updated_at=datetime.now(UTC), **self._site_columns(status))
        )

        try:
            result = await self._session.execute(statement)
        except SQLAlchemyError as e:
            msg = f"Failed to record the site's status of order {order_id}."
            raise RepoError(msg) from e

        return bool(getattr(result, "rowcount", 0))

    @override
    async def latest_site_update(self) -> datetime | None:
        statement = select(func.max(order_handovers_table.c.site_updated_at))

        try:
            value = (await self._session.execute(statement)).scalar_one_or_none()
        except SQLAlchemyError as e:
            msg = "Failed to read where the order feed stopped."
            raise RepoError(msg) from e

        return value if isinstance(value, datetime) else None

    @staticmethod
    def _site_columns(status: SiteOrderStatus) -> dict[str, object]:
        return {
            "site_order_id": status.site_order_id,
            "site_number": status.number[:64],
            "site_status_code": status.status_code[:20],
            "site_status_name": status.status_name[:255],
            "site_state": status.state.value,
            "site_updated_at": status.updated_at,
        }

    async def _update(self, order_id: OrderId, **values: object) -> None:
        statement = (
            update(order_handovers_table)
            .where(order_handovers_table.c.order_id == order_id)
            .values(updated_at=datetime.now(UTC), **values)
        )

        try:
            await self._session.execute(statement)
        except SQLAlchemyError as e:
            msg = f"Failed to update the handover of order {order_id}."
            raise RepoError(msg) from e
