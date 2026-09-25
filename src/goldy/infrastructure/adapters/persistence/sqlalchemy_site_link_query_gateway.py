import logging
from typing import TYPE_CHECKING, Final, final, override

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.users import SiteLinkQueryGateway
from goldy.application.common.views.site import SiteLinkView
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models import user_site_links_table

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class SqlAlchemySiteLinkQueryGateway(SiteLinkQueryGateway):
    """Reads one row of ``user_site_links`` by the primary key."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def read_for(self, user_id: UserId) -> SiteLinkView | None:
        statement = select(user_site_links_table).where(
            user_site_links_table.c.user_id == user_id,
        )

        try:
            row = (await self._session.execute(statement)).mappings().one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the site link")
            msg = "Failed to read the site link."
            raise RepoError(msg) from e

        if row is None:
            return None

        return SiteLinkView(
            customer_name=row["customer_name"],
            company_name=row["company_name"],
            is_wholesale=row["is_wholesale"],
            linked_at=row["linked_at"],
        )
