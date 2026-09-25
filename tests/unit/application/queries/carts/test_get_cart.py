"""Reading the cart screen: empty by default, then repriced for a linked customer.

``price_basis`` is what the screen must show and what checkout refuses on, so
every branch that sets it is a customer-visible fact and not an implementation
detail.
"""

from decimal import Decimal

from goldy.application.common.views.cart import CartView, PriceBasis
from goldy.application.common.views.money import MoneyView
from goldy.application.error import SiteUnavailableError
from goldy.application.queries.carts.get_cart.handler import GetCartHandler
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.domain.common.values.currency import Currency
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.factories.cart_factories import make_cart_line_view
from tests.unit.factories.shop_factories import make_money, make_product_id
from tests.unit.stubs.cart_query import InMemoryCartQueryGateway
from tests.unit.stubs.site import (
    InMemorySiteLinkQueryGateway,
    ScriptedSitePricing,
    site_link_view,
)

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}


def _cart_view(*, lines: int = 1, is_available: bool = True) -> CartView:
    return CartView(
        lines=tuple(
            make_cart_line_view(index, is_available=is_available)
            for index in range(1, lines + 1)
        ),
        total=MoneyView(amount=Decimal("19.99") * lines, currency=Currency.RUB.value),
    )


async def test_a_person_with_no_cart_row_sees_an_empty_cart(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    get_cart_handler: GetCartHandler,
) -> None:
    """Nobody has added anything yet, and this is not an error."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    view = await get_cart_handler.handle(GetCartQuery())

    assert view.is_empty is True
    assert view.total.amount == 0
    assert view.price_basis is PriceBasis.RETAIL


async def test_a_guest_sees_the_catalog_prices_the_gateway_joined(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    cart_query_gateway: InMemoryCartQueryGateway,
    get_cart_handler: GetCartHandler,
    site_pricing: ScriptedSitePricing,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    cart_query_gateway.views[customer.id] = _cart_view()

    view = await get_cart_handler.handle(GetCartQuery())

    assert view.price_basis is PriceBasis.RETAIL
    assert view.lines[0].unit_price is not None
    assert site_pricing.calls == []


async def test_the_cart_is_read_for_whoever_is_asking(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    cart_query_gateway: InMemoryCartQueryGateway,
    get_cart_handler: GetCartHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    cart_query_gateway.views[customer.id] = _cart_view()

    await get_cart_handler.handle(GetCartQuery())

    read_user_id, _ = cart_query_gateway.reads[0]
    assert read_user_id == customer.id


async def test_a_linked_customer_is_repriced_by_the_site(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    cart_query_gateway: InMemoryCartQueryGateway,
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
    get_cart_handler: GetCartHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    cart_query_gateway.views[customer.id] = _cart_view()
    site_links.links[customer.id] = site_link_view()
    site_pricing.prices = {make_product_id(1): make_money("15.00")}

    view = await get_cart_handler.handle(GetCartQuery())

    assert view.price_basis is PriceBasis.PERSONAL
    assert view.lines[0].unit_price is not None
    assert view.lines[0].unit_price.amount == make_money("15.00").amount
    assert view.total.amount == make_money("15.00").amount


async def test_a_line_the_site_will_not_price_shows_no_price(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    cart_query_gateway: InMemoryCartQueryGateway,
    site_links: InMemorySiteLinkQueryGateway,
    get_cart_handler: GetCartHandler,
) -> None:
    """The site refuses this position for this customer — hidden, archived, unpriced."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    cart_query_gateway.views[customer.id] = _cart_view()
    site_links.links[customer.id] = site_link_view()

    view = await get_cart_handler.handle(GetCartQuery())

    assert view.lines[0].unit_price is None
    assert view.lines[0].line_total is None
    assert view.total.amount == 0


async def test_an_unavailable_line_is_not_sent_to_the_site_to_be_priced(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    cart_query_gateway: InMemoryCartQueryGateway,
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
    get_cart_handler: GetCartHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    cart_query_gateway.views[customer.id] = _cart_view(is_available=False)
    site_links.links[customer.id] = site_link_view()

    await get_cart_handler.handle(GetCartQuery())

    assert site_pricing.calls == []


async def test_the_site_not_answering_falls_back_to_the_catalog_prices_and_says_so(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    cart_query_gateway: InMemoryCartQueryGateway,
    site_links: InMemorySiteLinkQueryGateway,
    site_pricing: ScriptedSitePricing,
    get_cart_handler: GetCartHandler,
) -> None:
    """Checkout refuses until the site is back; the screen has to say why."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    cart_query_gateway.views[customer.id] = _cart_view()
    site_links.links[customer.id] = site_link_view()
    site_pricing.errors = [SiteUnavailableError("timed out")]

    view = await get_cart_handler.handle(GetCartQuery())

    assert view.price_basis is PriceBasis.PERSONAL_UNAVAILABLE
    assert view.lines[0].unit_price is not None
