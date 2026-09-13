from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import RowMapping

    from goldy.application.common.views.cart import CartView


class CartRowViewMapper(Protocol):
    """Builds the cart screen out of the joined rows the cart query fetches.

    Kept in the infrastructure layer, port and all, because its input is a
    ``sqlalchemy.RowMapping`` — the reason every row mapper here lives where
    it does. Injected into the gateway rather than written inside it, so the
    query and the shape of what it becomes are two things, each replaceable
    on its own.

    Takes the whole result rather than one row, because the view carries a
    total over the lines and the total is this mapper's to compute: the rows
    are what the database said, the sum is a reading of them.
    """

    @abstractmethod
    def to_cart_view(self, rows: Sequence[RowMapping]) -> CartView:
        """Reads ``product_id`` and ``quantity``, the joined product, price and stock."""
        raise NotImplementedError
