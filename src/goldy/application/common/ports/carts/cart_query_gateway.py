from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.application.common.views.cart import CartView
    from goldy.domain.catalog.values.price_type_id import PriceTypeId
    from goldy.domain.users.values.user_id import UserId


class CartQueryGateway(Protocol):
    """Read-side DAO for the cart screen, prices and stock joined in SQL.

    The cart itself stores no prices — the price belongs to the projection and
    moves without us, while a cart lives for days — so everything but the
    quantities is joined on every render. That is what makes a new price list
    reprice an existing cart at once instead of leaving stale numbers in it.

    The join against the products is a ``LEFT JOIN`` and is taken **without an
    ``is_active`` filter**. This is written out here because the filter looks
    natural and somebody will add it during the first refactor: with it, a
    product withdrawn from the catalog would disappear from the screen and the
    total would quietly shrink, which is worse than an error — nobody notices
    what is not there. Instead the line comes back marked unavailable, the
    screen says so, and "checkout" stays hidden until it is dealt with.
    """

    @abstractmethod
    async def read_for(
        self,
        user_id: UserId,
        price_type_id: PriceTypeId,
    ) -> CartView | None:
        """This person's cart priced for them, or nothing if they have no row.

        ``None`` means there is no cart row at all, which is the ordinary state
        of somebody who has just registered. It is not an error and must not
        become one: the query turns it into an empty view, and the screen draws
        "your cart is empty".
        """
        raise NotImplementedError
