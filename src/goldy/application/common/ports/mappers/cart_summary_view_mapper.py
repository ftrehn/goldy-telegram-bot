from abc import abstractmethod
from typing import Protocol

from goldy.application.common.views.cart import CartSummaryView
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.catalog.values.product_id import ProductId


class CartSummaryViewMapper(Protocol):
    """Renders a changed cart as the view its commands return.

    Only counts cross, never the lines: the full cart screen is a join against
    the catalog and the prices, and building it inside the writing transaction
    would pay for a second query to produce an answer presentation discards —
    the screen re-reads itself through ``GetCartQuery`` on every render.

    ``changed_product_id`` is handed in rather than read off the aggregate
    because the aggregate does not know which of its lines the command just
    touched, and a command that touched all of them — emptying the cart —
    passes ``None``.

    The counterpart for orders deliberately does not exist. An order card is
    shown by its own query and not by the handler that placed the order, so a
    mapper for one call would only have added a sixth collaborator to a handler
    that already has five.
    """

    @abstractmethod
    def to_view(
        self,
        cart: Cart,
        changed_product_id: ProductId | None,
    ) -> CartSummaryView:
        raise NotImplementedError
