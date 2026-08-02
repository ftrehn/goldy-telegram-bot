from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from goldy.application.common.query_params.pagination import Pagination
    from goldy.application.common.query_params.sorting import SortingOrder
    from goldy.application.common.query_params.user_filters import UserFilters
    from goldy.application.common.views.user import UserView
    from goldy.domain.users.values.user_id import UserId


class UserQueryGateway(Protocol):
    """Read-side DAO for the admin screens.

    Returns views, never aggregates. A list of two hundred users exists to be
    rendered, not to have business rules run against it, and loading two
    hundred aggregates with their accounts to print a table is how the admin
    page gets slow.

    A protocol rather than a class so reads can be wrapped later — a caching
    decorator over this port is invisible to every handler that uses it.
    """

    @abstractmethod
    async def read_by_id(self, user_id: UserId) -> UserView | None:
        raise NotImplementedError

    @abstractmethod
    async def read_all(
        self,
        pagination: Pagination,
        sorting: SortingOrder,
        filters: UserFilters,
    ) -> Sequence[UserView]:
        raise NotImplementedError

    @abstractmethod
    async def total(self, filters: UserFilters) -> int:
        raise NotImplementedError
