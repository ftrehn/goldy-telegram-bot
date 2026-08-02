import logging
from datetime import UTC, datetime
from typing import Final, override
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.outbox.outbox_command_gateway import (
    OutboxCommandGateway,
)
from goldy.application.common.ports.outbox.outbox_message import OutboxMessage
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models.outbox import (
    OutboxRecord,
    outbox_messages_table,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyOutboxRepository(OutboxCommandGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def add(self, message: OutboxMessage) -> None:
        record = OutboxRecord(
            id=message.id,
            event_type=message.event_type,
            payload=message.payload,
            created_at=message.created_at,
        )
        try:
            self._session.add(record)
        except SQLAlchemyError as e:
            msg = "Failed to enqueue outbox message."
            raise RepoError(msg) from e
        logger.debug(
            "Outbox message enqueued: %s (type=%s)", message.id, message.event_type
        )

    @override
    async def read_pending(self, limit: int = 100) -> list[OutboxMessage]:
        try:
            result = await self._session.execute(
                select(OutboxRecord)
                .where(outbox_messages_table.c.processed_at.is_(None))
                .order_by(outbox_messages_table.c.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            records = result.scalars().all()
        except SQLAlchemyError as e:
            msg = "Failed to fetch pending outbox messages."
            raise RepoError(msg) from e
        return [
            OutboxMessage(
                id=r.id,
                event_type=r.event_type,
                payload=r.payload,
                created_at=r.created_at,
                processed_at=r.processed_at,
            )
            for r in records
        ]

    @override
    async def mark_processed(self, message_id: UUID) -> None:
        try:
            await self._session.execute(
                update(OutboxRecord)
                .where(outbox_messages_table.c.id == message_id)
                .values(processed_at=datetime.now(UTC))
            )
        except SQLAlchemyError as e:
            msg = "Failed to mark outbox message as processed."
            raise RepoError(msg) from e
        logger.debug("Outbox message marked as processed: %s", message_id)
