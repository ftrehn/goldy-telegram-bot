"""Stand-ins for the gateways an order use case talks to.

The command gateways hold aggregates by identity and hand back the *same*
object, which is what an identity-mapped session does: a handler that reads an
order and cancels it does not write it back, and the change is visible anyway.

The query gateway is a recorder rather than a filter. Which page a list handler
asked for, with which filters and for whose orders, is the interesting part of
it; reimplementing the SQL in Python here would only test the reimplementation.

The cart gateway lives here rather than with the cart use cases because placing
an order needs one, and ``ensure_for`` is the half of that port checkout uses:
it never fails on a missing cart, it creates one — which is exactly how a
second confirmation tap ends up meeting an empty cart instead of a missing one.
"""

from dataclasses import dataclass
from typing import Final, final, override
from uuid import UUID

from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.orders import (
    OrderCommandGateway,
    OrderQueryGateway,
)
from goldy.application.common.query_params.order_filters import (
    OrderFilters,
    OrderSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.views.order import OrderListView, OrderView
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.carts.values.cart_id import CartId
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.values.user_id import UserId


@dataclass(frozen=True, slots=True)
class OrdersRead:
    """One call to a listing method, kept whole so a test can name any part."""

    customer_id: UserId | None
    pagination: Pagination
    sorting: OrderSorting
    filters: OrderFilters


@final
class InMemoryCartCommandGateway(CartCommandGateway):
    """Carts by owner, one per person, created on demand like the real one."""

    def __init__(self, events_collection: EventsCollection) -> None:
        self._events_collection: Final[EventsCollection] = events_collection
        self.carts: dict[UserId, Cart] = {}
        self._next_cart: int = 1

    @override
    async def ensure_for(self, user_id: UserId) -> Cart:
        cart = self.carts.get(user_id)

        if cart is None:
            cart = Cart.create(
                cart_id=CartId(UUID(int=self._next_cart)),
                events_collection=self._events_collection,
                user_id=user_id,
            )
            self._next_cart += 1
            self.carts[user_id] = cart

        return cart

    @override
    async def by_user_id(self, user_id: UserId) -> Cart | None:
        return self.carts.get(user_id)


@final
class InMemoryOrderCommandGateway(OrderCommandGateway):
    """Orders by identity, with the inserts recorded in the order they came."""

    def __init__(self) -> None:
        self.orders: dict[OrderId, Order] = {}
        self.added: list[OrderId] = []

    @override
    async def add(self, order: Order) -> None:
        self.orders[order.id] = order
        self.added.append(order.id)

    @override
    async def by_id(self, order_id: OrderId) -> Order | None:
        return self.orders.get(order_id)


@final
class StubOrderQueryGateway(OrderQueryGateway):
    """Answers reads from whatever a test put in it, recording every call."""

    def __init__(self) -> None:
        self.cards: dict[OrderId, OrderView] = {}
        self.listing: OrderListView = OrderListView(orders=(), total=0)
        self.last_delivery_address: str | None = None
        self.reads: list[OrdersRead] = []
        self.address_reads: list[UserId] = []

    @override
    async def read_by_id(self, order_id: OrderId) -> OrderView | None:
        return self.cards.get(order_id)

    @override
    async def read_for_customer(
        self,
        *,
        customer_id: UserId,
        pagination: Pagination,
        sorting: OrderSorting,
        filters: OrderFilters,
    ) -> OrderListView:
        self.reads.append(
            OrdersRead(
                customer_id=customer_id,
                pagination=pagination,
                sorting=sorting,
                filters=filters,
            ),
        )
        return self.listing

    @override
    async def read_all(
        self,
        *,
        pagination: Pagination,
        sorting: OrderSorting,
        filters: OrderFilters,
    ) -> OrderListView:
        self.reads.append(
            OrdersRead(
                customer_id=None,
                pagination=pagination,
                sorting=sorting,
                filters=filters,
            ),
        )
        return self.listing

    @override
    async def read_last_delivery_address(self, customer_id: UserId) -> str | None:
        self.address_reads.append(customer_id)
        return self.last_delivery_address
