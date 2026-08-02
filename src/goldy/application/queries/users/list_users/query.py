from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.user import UserListView
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus


@dataclass(frozen=True, slots=True)
class ListUsersQuery(Query[UserListView]):
    """One page of the admin user list.

    Sorted by registration time, newest first by default — the admin side is
    used to find someone who just wrote in far more often than to browse the
    whole book.
    """

    limit: int | None = None
    offset: int | None = None
    sorting: SortingOrder = SortingOrder.DESC
    role: UserRole | None = None
    status: UserStatus | None = None
    search: str | None = None
