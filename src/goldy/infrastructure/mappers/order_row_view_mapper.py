from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import RowMapping

    from goldy.application.common.views.order import (
        OrderLineView,
        OrderListItemView,
        OrderView,
    )


class OrderRowViewMapper(Protocol):
    """Builds the order read model straight from result rows.

    Kept in the infrastructure layer, port and all, because its input is a
    ``sqlalchemy.RowMapping``: declaring this among the application ports would
    put the ORM in the layer that is meant not to know one — the same reason
    ``UserRowViewMapper`` lives here.

    Three methods rather than one, because an order card, one of its lines and
    a row of a list are three different shapes of row. The card is assembled in
    two queries — the order, then its lines — so the lines arrive already
    mapped and are grafted on, exactly as a user's messenger accounts are.
    """

    @abstractmethod
    def to_view(self, row: RowMapping, lines: Sequence[OrderLineView]) -> OrderView:
        raise NotImplementedError

    @abstractmethod
    def to_line_view(self, row: RowMapping) -> OrderLineView:
        raise NotImplementedError

    @abstractmethod
    def to_list_item_view(self, row: RowMapping) -> OrderListItemView:
        raise NotImplementedError
