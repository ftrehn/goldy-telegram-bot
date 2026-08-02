from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.user import UserView


@dataclass(frozen=True, slots=True)
class GetUserByIdQuery(Query[UserView]):
    """One person's card on the admin side."""

    user_id: UUID
