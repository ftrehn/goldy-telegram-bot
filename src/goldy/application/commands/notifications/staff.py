from uuid import UUID

from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.application.common.views.user import UserView
from goldy.domain.users.services.authorization.role_hierarchy import STAFF_ROLES


async def read_staff(user_query_gateway: UserQueryGateway) -> list[UserView]:
    """Everyone in a role that works orders, each of them once.

    One query per role and a deduplication rather than one query with a role
    list, because ``UserFilters`` narrows by a single role — and an
    administrator who is also on the managers' screen must still get one
    message.
    """
    found: dict[UUID, UserView] = {}

    for role in sorted(STAFF_ROLES):
        people = await user_query_gateway.read_all(
            Pagination(),
            SortingOrder.ASC,
            UserFilters(role=role),
        )
        found.update({person.id: person for person in people})

    return list(found.values())
