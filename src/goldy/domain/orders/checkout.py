from dataclasses import dataclass
from typing import final

from goldy.domain.carts.entities.cart import Cart
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.priced_product import PricedProduct
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_comment import OrderComment
from goldy.domain.orders.values.recipient import Recipient


@final
@dataclass(frozen=True, kw_only=True)
class Checkout:
    """What ``CheckoutService`` is given to turn a cart into an order.

    ``priced_products`` is what the handler has just read out of the catalog
    projection for this customer's price type. The service takes prices from
    here and from nowhere else, which is what makes the snapshot in the order
    the thing the customer was actually shown.
    """

    cart: Cart
    priced_products: tuple[PricedProduct, ...]
    delivery_address: DeliveryAddress
    recipient: Recipient
    comment: OrderComment | None
    price_type_id: PriceTypeId
