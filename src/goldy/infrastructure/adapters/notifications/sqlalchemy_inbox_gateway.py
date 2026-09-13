import logging
from datetime import UTC, datetime
from typing import Final, final, override
from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.notifications import InboxGateway
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models.inbox import inbox_messages_table

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class SqlAlchemyInboxGateway(InboxGateway):
    """Claims broker messages with one insert inside a savepoint.

    A plain Core ``INSERT`` and the primary key doing the deciding. A read
    followed by a write would be two statements with a gap between them, and
    two workers pulling the same redelivered message both read nothing and
    both write — which is the duplicate this table exists to prevent. The
    database resolves the clash against the primary key, and the
    ``IntegrityError`` is what tells the loser it wrote nothing.

    Written against Core rather than the Postgres dialect on purpose. The
    obvious spelling is ``INSERT ... ON CONFLICT DO NOTHING``, and it is
    Postgres-only; the savepoint costs one round trip more and works on any
    database SQLAlchemy speaks. The savepoint is also what keeps the session
    usable after the refused insert — a failed statement outside one leaves
    the transaction rollback-only, and the claim rides the caller's.

    The claim rides that transaction, which the command pipeline opens and
    commits. That is what ties "we handled this" to whatever handling it
    caused: a send that raises rolls the claim back, and the redelivered
    message is free to be claimed again.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def claim(self, message_id: UUID, event_type: str) -> bool:
        statement = insert(inbox_messages_table).values(
            id=message_id,
            event_type=event_type,
            processed_at=datetime.now(UTC),
        )

        try:
            async with self._session.begin_nested():
                await self._session.execute(statement)
        except IntegrityError:
            logger.debug("inbox: message %s (%s) already handled", message_id, event_type)
            return False
        except SQLAlchemyError as exc:
            msg = f"Failed to claim inbox message {message_id}."
            raise RepoError(msg) from exc

        logger.debug("inbox: message %s (%s) claimed", message_id, event_type)
        return True
