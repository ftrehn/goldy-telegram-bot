"""The shop the scenarios buy from, and the command that buys from it.

One builder rather than a snapshot spelled out in each file, because every
scenario here starts from the same shop and differs in what happens to it
afterwards: a price moves, a product is withdrawn, a customer is bound to
another price list. Spelling the baseline out six times would bury that
difference in the noise around it.

Two price lists in every snapshot on purpose. The wholesale one is what the bot
is configured to fall back to, the retail one is what a binding can point at,
and a shop that only ever had one would let a scenario pass while resolving the
wrong list — there would be nothing else for it to resolve.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from goldy.application.commands.orders.place_order.command import PlaceOrderCommand
from goldy.application.common.ports.catalog import CatalogSnapshot, PriceTypeBindingRow
from goldy.application.common.views.cart import CartView
from tests.unit.factories.catalog_factories import (
    BATCH_ID,
    make_category_row,
    make_price_row,
    make_price_type_row,
    make_product_row,
    make_snapshot,
    make_stock_row,
)
from tests.unit.factories.domain_factories import CUSTOMER_PHONE
from tests.unit.factories.shop_factories import (
    DELIVERY_ADDRESS,
    RECIPIENT_FIRST_NAME,
    RECIPIENT_LAST_NAME,
)

RETAIL_PRICE_TYPE_ID: Final[str] = "1c-price-type-retail"
SECOND_BATCH_ID: Final[str] = "batch-0002"
THIRD_BATCH_ID: Final[str] = "batch-0003"

WHOLESALE_PRICES: Final[Mapping[int, str]] = {1: "100.00", 2: "50.00"}
"""What the configured default price list charges for each product."""

RETAIL_PRICES: Final[Mapping[int, str]] = {1: "150.00", 2: "75.00"}
"""What a customer bound to the other list is charged instead."""

STOCK: Final[Mapping[int, str]] = {1: "10", 2: "0"}
"""Product 2 is deliberately at zero: it is sold to order, not hidden."""


def a_shop(
    batch_id: str = BATCH_ID,
    products: Sequence[int] = (1, 2),
    wholesale: Mapping[int, str] | None = None,
    retail: Mapping[int, str] | None = None,
    stock: Mapping[int, str] | None = None,
    bindings: Sequence[PriceTypeBindingRow] = (),
) -> CatalogSnapshot:
    """One run of the exchange: a group, its products, two price lists, stock.

    Prices are keyed by product number rather than listed as rows so that a
    scenario changing one price says exactly that and inherits the rest.
    """
    priced = WHOLESALE_PRICES if wholesale is None else wholesale
    retailed = RETAIL_PRICES if retail is None else retail
    on_hand = STOCK if stock is None else stock

    return make_snapshot(
        batch_id=batch_id,
        categories=(make_category_row(1),),
        products=tuple(make_product_row(index) for index in products),
        price_types=(make_price_type_row(), make_price_type_row(RETAIL_PRICE_TYPE_ID)),
        prices=(
            *(make_price_row(index, amount=amount) for index, amount in priced.items()),
            *(
                make_price_row(index, amount=amount, price_type_id=RETAIL_PRICE_TYPE_ID)
                for index, amount in retailed.items()
            ),
        ),
        stock=tuple(
            make_stock_row(index, quantity=quantity)
            for index, quantity in on_hand.items()
        ),
        bindings=tuple(bindings),
    )


def a_checkout(
    cart: CartView,
    address: str = DELIVERY_ADDRESS,
    comment: str | None = None,
) -> PlaceOrderCommand:
    """The command the confirmation screen builds, read back off that screen.

    The totals come from the cart the test last looked at rather than from what
    the catalog says now, because that is the whole point of them: the getter
    reads them off the window the customer is looking at, and a scenario that
    recomputed them would never be able to show a repricing being refused.
    """
    return PlaceOrderCommand(
        delivery_address=address,
        recipient_first_name=RECIPIENT_FIRST_NAME,
        recipient_last_name=RECIPIENT_LAST_NAME,
        recipient_phone_number=CUSTOMER_PHONE,
        comment=comment,
        expected_total=cart.total.amount,
        expected_line_count=cart.line_count,
    )
