"""Stand-in for the cart screen's read-side gateway.

A dictionary keyed by user id, the same identity-by-owner shape the write side
gateway uses — the price type argument is recorded rather than acted on, since
production applies it in the join this stub exists to avoid reimplementing.
"""

from typing import final, override

from goldy.application.common.ports.carts import CartQueryGateway
from goldy.application.common.views.cart import CartView
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.users.values.user_id import UserId


@final
class InMemoryCartQueryGateway(CartQueryGateway):
    """Answers with whatever view a test put in, or nothing for no cart row."""

    def __init__(self) -> None:
        self.views: dict[UserId, CartView] = {}
        self.reads: list[tuple[UserId, PriceTypeId]] = []

    @override
    async def read_for(
        self,
        user_id: UserId,
        price_type_id: PriceTypeId,
    ) -> CartView | None:
        self.reads.append((user_id, price_type_id))
        return self.views.get(user_id)
