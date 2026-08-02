from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import RowMapping

    from goldy.application.common.views.user import MessengerAccountView, UserView


class UserRowViewMapper(Protocol):
    """Builds the user read model straight from result rows.

    Kept in the infrastructure layer, port and all, because its input is a
    ``sqlalchemy.RowMapping``: declaring this among the application ports would
    put the ORM in the layer that is meant not to know one.
    """

    @abstractmethod
    def to_view(
        self,
        row: RowMapping,
        accounts: Sequence[MessengerAccountView],
    ) -> UserView:
        raise NotImplementedError

    @abstractmethod
    def to_account_view(self, row: RowMapping) -> MessengerAccountView:
        raise NotImplementedError
