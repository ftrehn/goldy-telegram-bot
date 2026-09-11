import logging
from datetime import UTC, datetime
from typing import Final, final, override
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.notifications import InboxGateway
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models.inbox import inbox_messages_table

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class SqlAlchemyInboxGateway(InboxGateway):
    """Claims broker messages with a single conditional insert.

    ``INSERT ... ON CONFLICT (id) DO NOTHING RETURNING id`` and nothing else. A
    read followed by a write would be two statements with a gap between them,
    and two workers pulling the same redelivered message both read nothing and
    both write — which is the duplicate this table exists to prevent. Postgres
    resolves the conflict against the primary key, and ``RETURNING`` is what
    tells the loser it wrote nothing: a conflicting insert yields no row.

    The claim rides the caller's transaction, which the command pipeline opens
    and commits. That is what ties "we handled this" to whatever handling it
    caused: a send that raises rolls the claim back, and the redelivered
    message is free to be claimed again.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def claim(self, message_id: UUID, event_type: str) -> bool:
        statement = (
            postgresql_insert(inbox_messages_table)
            .values(
                id=message_id,
                event_type=event_type,
                processed_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(inbox_messages_table.c.id)
        )

        try:
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            msg = f"Failed to claim inbox message {message_id}."
            raise RepoError(msg) from exc

        claimed = result.scalar_one_or_none() is not None

        logger.debug(
            "inbox: message %s (%s) %s",
            message_id,
            event_type,
            "claimed" if claimed else "already handled",
        )
        return claimed
