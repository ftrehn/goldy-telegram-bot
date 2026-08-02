from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.user import UserView


@dataclass(frozen=True, slots=True)
class GetCurrentUserQuery(Query[UserView]):
    """Whoever is talking to the bot right now.

    Carries no fields: the identity comes from the update being handled, and
    accepting a user id here would let anyone read anyone.
    """
